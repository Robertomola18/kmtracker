import logging
import os
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ConversationHandler, TypeHandler, ApplicationHandlerStop, filters, ContextTypes
)
from models import (
    get_all_cars, get_car, add_entry, preview_entry, add_fuel, add_expense,
    get_maintenance_items, add_maintenance_item, update_maintenance_item,
    delete_maintenance_item, get_active_alerts, get_renewal_alerts,
    get_consumption, get_km_mes, get_gasto_mes, get_euro_per_km,
    get_total_expenses, get_setting,
)

logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

TOKEN = os.environ.get('TELEGRAM_TOKEN', '')


def allowed_user_ids():
    """IDs de Telegram autorizados (lista blanca).

    Se leen de TELEGRAM_ALLOWED_USER_IDS (coma/espacio separados) o, si no,
    del ajuste 'telegram_allowed_ids' de la BD. Si la lista esta vacia el bot
    queda ABIERTO (solo recomendable en pruebas): se avisa por log."""
    raw = os.environ.get('TELEGRAM_ALLOWED_USER_IDS') or ''
    if not raw:
        try:
            raw = get_setting('telegram_allowed_ids', '') or ''
        except Exception:
            raw = ''
    ids = set()
    for part in raw.replace(';', ',').replace(' ', ',').split(','):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                logger.warning('ID de Telegram ignorado (no numerico): %r', part)
    return ids


async def _auth_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bloquea a cualquier usuario que no este en la lista blanca."""
    ids = allowed_user_ids()
    if not ids:
        return  # sin lista blanca configurada: no se bloquea
    user = update.effective_user
    if user and user.id in ids:
        return
    uid = user.id if user else '?'
    logger.warning('Acceso no autorizado al bot (user_id=%s)', uid)
    try:
        if update.callback_query:
            await update.callback_query.answer('No autorizado.', show_alert=True)
        elif update.effective_message:
            await update.effective_message.reply_text(
                'No autorizado. Pide que te añadan a TELEGRAM_ALLOWED_USER_IDS.')
    except Exception:
        pass
    raise ApplicationHandlerStop


# --- States ---
(CAR_SELECT, KM_TYPE, KM_READING, KM_RESET, KM_CONFIRM,
 FUEL_LITROS, FUEL_PRECIO, FUEL_KM, FUEL_LLENO, FUEL_CONFIRM,
 EXPENSE_CONCEPT, EXPENSE_COST, EXPENSE_CAT, EXPENSE_CONFIRM,
 MAINT_ACTION, MAINT_ITEM_SELECT, MAINT_NAME, MAINT_INTERVAL, MAINT_DEL_CONFIRM,
 CHECK_CAR_SELECT) = range(20)

# --- Helpers ---
def _car_estado(c):
    """Sufijo de estado para el teclado: los coches excluidos o vendidos se
    marcan, pero siguen accesibles para consultar o anadir historico."""
    if c.get('es_prueba'):
        return " (prueba)"
    fb = c.get('fecha_baja')
    if fb and fb <= date.today().isoformat():
        return f" (vendido {fb})"
    return ""


def car_kb():
    kb = [[InlineKeyboardButton(f"{c['matricula']} · {c['modelo']}{_car_estado(c)}", callback_data=f"car_{c['id']}")]
          for c in get_all_cars()]
    return InlineKeyboardMarkup(kb)

def yes_no_kb(prefix):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Si", callback_data=f"{prefix}_yes"),
         InlineKeyboardButton("No", callback_data=f"{prefix}_no")]
    ])

def confirm_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Confirmar", callback_data="confirm_yes"),
         InlineKeyboardButton("Cancelar", callback_data="confirm_no")]
    ])

def cancel_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Cancelar", callback_data="cancel")]
    ])

def main_menu_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🚗 /km"), KeyboardButton("⛽ /repostar")],
        [KeyboardButton("💸 /gasto"), KeyboardButton("🛠 /mantenimiento")],
        [KeyboardButton("📋 /check"), KeyboardButton("🔔 /alertas")],
        [KeyboardButton("🏠 Menu")],
    ], resize_keyboard=True, input_field_placeholder="Selecciona una opcion...")

def km_type_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Parcial", callback_data="km_partial"),
         InlineKeyboardButton("Total", callback_data="km_total")]
    ])

def cat_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Seguro", callback_data="cat_seguro"),
         InlineKeyboardButton("ITV", callback_data="cat_itv"),
         InlineKeyboardButton("Impuesto", callback_data="cat_impuesto")],
        [InlineKeyboardButton("Taller", callback_data="cat_reparacion"),
         InlineKeyboardButton("Otro", callback_data="cat_otro")]
    ])

def maint_action_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Anadir", callback_data="maint_add"),
         InlineKeyboardButton("Modificar", callback_data="maint_edit")],
        [InlineKeyboardButton("Eliminar", callback_data="maint_del"),
         InlineKeyboardButton("Volver", callback_data="cancel")]
    ])

def maint_item_kb(car_id, action):
    items = get_maintenance_items(car_id)
    kb = [[InlineKeyboardButton(i['nombre'], callback_data=f"mitem_{i['id']}_{action}")] for i in items]
    kb.append([InlineKeyboardButton("Volver", callback_data="cancel")])
    return InlineKeyboardMarkup(kb)

def km_alert_text(car_id):
    alerts = get_active_alerts(car_id)
    lines = []
    for a in alerts:
        kr = a['km_restante']
        if kr < 0:
            lines.append(f"  {a['nombre']}: VENCIO ({'%.0f' % -kr} km excedidos)")
        elif kr <= 500:
            lines.append(f"  {a['nombre']}: {kr:.0f} km")
        else:
            lines.append(f"  {a['nombre']}: {kr:.0f} km")
    return '\n'.join(lines)

def format_check(car_id):
    car = get_car(car_id=car_id)
    if not car:
        return "Coche no encontrado."
    now = date.today()
    km_mes = get_km_mes(car_id, now.year, now.month)
    consumo = get_consumption(car_id)
    gasto = get_gasto_mes(car_id, now.year, now.month)
    eur_km = get_euro_per_km(car_id)
    total_exp = get_total_expenses(car_id)
    alerts = get_active_alerts(car_id)
    renewals = get_renewal_alerts(car_id)

    lines = [f"{car['modelo']} · {car['matricula']}"]
    lines.append(f"  Total: {'%.0f' % car['km_actual']} km")
    lines.append(f"  Este mes: {'%.0f' % km_mes} km")
    if consumo:
        lines.append(f"  Consumo: {consumo} L/100km")
    lines.append(f"  Gasto mes: {gasto:.2f} EUR")
    if eur_km:
        lines.append(f"  Coste total/km: {eur_km:.4f} EUR")
    lines.append(f"  Gasto total: {total_exp:.2f} EUR")

    if alerts:
        lines.append("")
        for a in alerts:
            kr = a['km_restante']
            if kr < 0:
                lines.append(f"  {a['nombre']}: VENCIO ({'%.0f' % -kr} km)")
            elif kr <= 3000:
                lines.append(f"  {a['nombre']}: {kr:.0f} km")

    if renewals:
        lines.append("")
        for r in renewals:
            if r['dias_restantes'] < 0:
                lines.append(f"  {r['tipo']}: VENCIO hace {-r['dias_restantes']} dias")
            else:
                lines.append(f"  {r['tipo']}: vence {r['fecha']} ({r['dias_restantes']} dias)")

    return '\n'.join(lines)

# --- /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🚗 *KMtracker Bot* 🚗\n\n"
        "📌 *Registros*\n"
        "  🚗 `/km` — Registrar viaje\n"
        "  ⛽ `/repostar` — Registrar repostaje\n"
        "  💸 `/gasto` — Registrar gasto\n\n"
        "🔧 *Gestion*\n"
        "  🛠 `/mantenimiento` — Items de mantenimiento\n"
        "  📋 `/check` — Resumen del coche\n"
        "  🔔 `/alertas` — Alertas de todos los coches\n\n"
        "❌ `/cancel` — Cancelar operacion"
    )
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=main_menu_kb())

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Menu:", reply_markup=main_menu_kb())

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Operacion cancelada.", reply_markup=InlineKeyboardMarkup([]))
    return ConversationHandler.END

async def cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Operacion cancelada.")
    context.user_data.clear()
    return ConversationHandler.END

# --- /km ---
async def km_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selecciona coche:", reply_markup=car_kb())
    return CAR_SELECT

async def km_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    car_id = int(query.data.split('_')[1])
    context.user_data['car_id'] = car_id
    car = get_car(car_id=car_id)
    await query.edit_message_text(f"{car['modelo']} · {car['matricula']}\nComo registras?", reply_markup=km_type_kb())
    return KM_TYPE

async def km_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tipo = query.data.split('_')[1]
    context.user_data['km_tipo'] = tipo
    label = "parcial" if tipo == "partial" else "odometro"
    await query.edit_message_text(f"Decime la lectura del {label}:", reply_markup=cancel_kb())
    return KM_READING

async def km_reading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        lectura = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Introduce un numero valido.", reply_markup=cancel_kb())
        return KM_READING
    context.user_data['km_lectura'] = lectura
    if context.user_data.get('km_tipo') == 'partial':
        await update.message.reply_text("Reseteaste el parcial?", reply_markup=yes_no_kb("reset"))
        return KM_RESET
    return await km_confirm(update, context)

async def km_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['km_reset'] = query.data == 'reset_yes'
    return await km_confirm(update, context)

async def km_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    car = get_car(car_id=context.user_data['car_id'])
    lectura = context.user_data['km_lectura']
    tipo = context.user_data.get('km_tipo', 'partial')
    car_id = context.user_data['car_id']
    result, error = preview_entry(car_id, tipo, lectura, context.user_data.get('km_reset', False))
    if error:
        text = f"Error: {error}"
        await (update.callback_query.edit_message_text(text) if update.callback_query
               else update.message.reply_text(text))
        return ConversationHandler.END
    context.user_data['km_result'] = result
    context.user_data['km_preview'] = {'tipo': tipo, 'lectura': lectura, 'is_reset': context.user_data.get('km_reset', False)}
    alerts = km_alert_text(car_id)
    text = (
        f"{car['modelo']} · {car['matricula']}\n"
        f"Mas: +{'%.0f' % result['km_calculados']} km\n"
        f"Total: {'%.0f' % result['km_acumulado']} km"
    )
    if alerts:
        text += f"\n\n{alerts}"
    msg = await (update.callback_query.edit_message_text(text, reply_markup=confirm_kb())
                 if update.callback_query
                 else update.message.reply_text(text, reply_markup=confirm_kb()))
    context.user_data['confirm_msg'] = msg
    context.user_data['confirm_action'] = 'km'
    return KM_CONFIRM

async def km_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    preview = context.user_data.get('km_preview', {})
    add_entry(context.user_data['car_id'], date.today().isoformat(),
              preview['tipo'], preview['lectura'], preview['is_reset'])
    await query.edit_message_text("Viaje registrado.")
    context.user_data.clear()
    return ConversationHandler.END

async def km_confirm_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("Operacion cancelada.")
    return ConversationHandler.END

# --- /repostar ---
async def fuel_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selecciona coche:", reply_markup=car_kb())
    return CAR_SELECT

async def fuel_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    car_id = int(query.data.split('_')[1])
    context.user_data['car_id'] = car_id
    car = get_car(car_id=car_id)
    await query.edit_message_text(f"{car['modelo']} · {car['matricula']}\nLitros:", reply_markup=cancel_kb())
    return FUEL_LITROS

async def fuel_litros(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        litros = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Introduce un numero valido.", reply_markup=cancel_kb())
        return FUEL_LITROS
    context.user_data['fuel_litros'] = litros
    await update.message.reply_text("Precio por litro (EUR):", reply_markup=cancel_kb())
    return FUEL_PRECIO

async def fuel_precio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        precio = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Introduce un numero valido.", reply_markup=cancel_kb())
        return FUEL_PRECIO
    context.user_data['fuel_precio'] = precio
    await update.message.reply_text("Km en el odometro:", reply_markup=cancel_kb())
    return FUEL_KM

async def fuel_km(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        km = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Introduce un numero valido.", reply_markup=cancel_kb())
        return FUEL_KM
    context.user_data['fuel_km'] = km
    await update.message.reply_text("Tanque lleno?", reply_markup=yes_no_kb("lleno"))
    return FUEL_LLENO

async def fuel_lleno(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['fuel_lleno'] = query.data == 'lleno_yes'
    car = get_car(car_id=context.user_data['car_id'])
    litros = context.user_data['fuel_litros']
    precio = context.user_data['fuel_precio']
    total = litros * precio
    text = (
        f"{car['modelo']} · {car['matricula']}\n"
        f"{litros}L x {precio} EUR = {total:.2f} EUR\n"
        f"Km: {context.user_data['fuel_km']:.0f}"
    )
    await query.edit_message_text(text, reply_markup=confirm_kb())
    context.user_data['confirm_action'] = 'fuel'
    return FUEL_CONFIRM

async def fuel_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    car_id = context.user_data['car_id']
    add_fuel(car_id, date.today().isoformat(), context.user_data['fuel_litros'],
             context.user_data['fuel_precio'], context.user_data['fuel_km'],
             'diesel', context.user_data.get('fuel_lleno', False))
    await query.edit_message_text("Repostaje registrado.")
    context.user_data.clear()
    return ConversationHandler.END

# --- /gasto ---
async def expense_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selecciona coche:", reply_markup=car_kb())
    return CAR_SELECT

async def expense_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    car_id = int(query.data.split('_')[1])
    context.user_data['car_id'] = car_id
    car = get_car(car_id=car_id)
    await query.edit_message_text(f"{car['modelo']} · {car['matricula']}\nConcepto:", reply_markup=cancel_kb())
    return EXPENSE_CONCEPT

async def expense_concept(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['exp_concept'] = update.message.text.strip()
    await update.message.reply_text("Importe (EUR):", reply_markup=cancel_kb())
    return EXPENSE_COST

async def expense_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        coste = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Introduce un numero valido.", reply_markup=cancel_kb())
        return EXPENSE_COST
    context.user_data['exp_cost'] = coste
    await update.message.reply_text("Categoria:", reply_markup=cat_kb())
    return EXPENSE_CAT

async def expense_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data.split('_')[1]
    context.user_data['exp_cat'] = cat
    car = get_car(car_id=context.user_data['car_id'])
    text = (
        f"{car['modelo']} · {car['matricula']}\n"
        f"{context.user_data['exp_concept']}: {context.user_data['exp_cost']:.2f} EUR"
    )
    await query.edit_message_text(text, reply_markup=confirm_kb())
    context.user_data['confirm_action'] = 'expense'
    return EXPENSE_CONFIRM

async def expense_confirm_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    add_expense(context.user_data['car_id'], date.today().isoformat(),
                context.user_data['exp_concept'], context.user_data['exp_cost'],
                context.user_data['exp_cat'])
    await query.edit_message_text("Gasto registrado.")
    context.user_data.clear()
    return ConversationHandler.END

# --- /mantenimiento ---
async def maint_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selecciona coche:", reply_markup=car_kb())
    return CAR_SELECT

async def maint_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    car_id = int(query.data.split('_')[1])
    context.user_data['car_id'] = car_id
    car = get_car(car_id=car_id)
    items = get_maintenance_items(car_id)
    lines = [f"{car['modelo']} · {car['matricula']}"]
    for i in items:
        kr = i['km_restante']
        if kr < 0:
            lines.append(f"  {i['nombre']}: VENCIO ({'%.0f' % -kr} km)")
        elif kr <= 3000:
            lines.append(f"  {i['nombre']}: {'%.0f' % kr} km")
        else:
            lines.append(f"  {i['nombre']}: {'%.0f' % kr} km")
    text = '\n'.join(lines) if items else "Sin items de mantenimiento."
    await query.edit_message_text(text, reply_markup=maint_action_kb())
    return MAINT_ACTION

async def maint_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data.split('_')[1]
    context.user_data['maint_action'] = action
    if action == 'add':
        await query.edit_message_text("Nombre del nuevo item:", reply_markup=cancel_kb())
        return MAINT_NAME
    elif action in ('edit', 'del'):
        await query.edit_message_text("Selecciona item:", reply_markup=maint_item_kb(context.user_data['car_id'], action))
        return MAINT_ITEM_SELECT
    return ConversationHandler.END

async def maint_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    item = context.user_data.get('maint_edit_item')
    if item:
        context.user_data['maint_new_name'] = name if name != '.' else item.get('nombre', '')
        cur_int = item.get('intervalo_km', 0)
        await update.message.reply_text(
            f"Nuevo intervalo (o . para dejar igual, actual: {'%.0f' % cur_int} km):",
            reply_markup=cancel_kb())
    else:
        context.user_data['maint_name'] = name
        await update.message.reply_text("Intervalo (km):", reply_markup=cancel_kb())
    return MAINT_INTERVAL

async def maint_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        interval = float(update.message.text)
    except ValueError:
        await update.message.reply_text("Introduce un numero valido.", reply_markup=cancel_kb())
        return MAINT_INTERVAL
    item = context.user_data.get('maint_edit_item')
    if item:
        name = context.user_data.get('maint_new_name', item.get('nombre', ''))
        update_maintenance_item(item['id'], name, interval, item.get('km_ultimo', 0))
        await update.message.reply_text(f"Item actualizado: {name} (cada {'%.0f' % interval} km)")
    else:
        add_maintenance_item(context.user_data['car_id'], context.user_data['maint_name'], interval)
        await update.message.reply_text(f"Item anadido: {context.user_data['maint_name']} (cada {'%.0f' % interval} km)")
    context.user_data.clear()
    return ConversationHandler.END

async def maint_item_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split('_')
    item_id = int(parts[1])
    action = parts[2]
    context.user_data['maint_item_id'] = item_id
    items = get_maintenance_items(car_id=context.user_data['car_id'])
    item = next((i for i in items if i['id'] == item_id), None)
    if not item:
        await query.edit_message_text("Item no encontrado.")
        return ConversationHandler.END

    if action == 'edit':
        context.user_data['maint_edit_item'] = item
        await query.edit_message_text(
            f"Editando: {item['nombre']}\n"
            f"Nuevo nombre (o . para dejar igual):",
            reply_markup=cancel_kb())
        return MAINT_NAME
    else:
        await query.edit_message_text(
            f"Eliminar {item['nombre']}?",
            reply_markup=yes_no_kb("maint_del"))
        return MAINT_DEL_CONFIRM



async def maint_del_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'maint_del_yes':
        delete_maintenance_item(context.user_data['maint_item_id'])
        await query.edit_message_text("Item eliminado.")
    else:
        await query.edit_message_text("Eliminacion cancelada.")
    context.user_data.clear()
    return ConversationHandler.END

# --- /check ---
async def check_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Selecciona coche:", reply_markup=car_kb())
    return CHECK_CAR_SELECT

async def check_car(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    car_id = int(query.data.split('_')[1])
    text = format_check(car_id)
    await query.edit_message_text(text)
    context.user_data.clear()
    return ConversationHandler.END

# --- /alertas ---
async def alertas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = get_active_alerts()
    renewals = get_renewal_alerts()
    lines = []
    if alerts:
        lines.append("Mantenimiento:")
        for a in alerts:
            kr = a['km_restante']
            if kr < 0:
                lines.append(f"  {a['modelo']} · {a['nombre']}: VENCIO ({'%.0f' % -kr} km)")
            else:
                lines.append(f"  {a['modelo']} · {a['nombre']}: {kr:.0f} km")
    if renewals:
        if lines:
            lines.append("")
        lines.append("Renovaciones:")
        for r in renewals:
            if r['dias_restantes'] < 0:
                lines.append(f"  {r['modelo']} · {r['tipo']}: VENCIO hace {-r['dias_restantes']} dias")
            else:
                lines.append(f"  {r['modelo']} · {r['tipo']}: vence {r['fecha']} ({r['dias_restantes']} dias)")
    if not lines:
        lines.append("Sin alertas.")
    await update.message.reply_text('\n'.join(lines))

# --- Main ---
def get_handlers():
    km_conv = ConversationHandler(
        entry_points=[CommandHandler('km', km_start), MessageHandler(filters.Text(['🚗 /km']), km_start)],
        states={
            CAR_SELECT: [CallbackQueryHandler(km_car, pattern=r'^car_\d+$')],
            KM_TYPE: [CallbackQueryHandler(km_type, pattern=r'^km_(partial|total)$')],
            KM_READING: [MessageHandler(filters.TEXT & ~filters.COMMAND, km_reading),
                         CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            KM_RESET: [CallbackQueryHandler(km_reset, pattern=r'^reset_(yes|no)$')],
            KM_CONFIRM: [CallbackQueryHandler(km_confirm_yes, pattern=r'^confirm_yes$'),
                         CallbackQueryHandler(km_confirm_no, pattern=r'^confirm_no$')],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
        name="km_conversation",
        persistent=False,
    )

    fuel_conv = ConversationHandler(
        entry_points=[CommandHandler('repostar', fuel_start), MessageHandler(filters.Text(['⛽ /repostar']), fuel_start)],
        states={
            CAR_SELECT: [CallbackQueryHandler(fuel_car, pattern=r'^car_\d+$')],
            FUEL_LITROS: [MessageHandler(filters.TEXT & ~filters.COMMAND, fuel_litros),
                          CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            FUEL_PRECIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fuel_precio),
                          CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            FUEL_KM: [MessageHandler(filters.TEXT & ~filters.COMMAND, fuel_km),
                      CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            FUEL_LLENO: [CallbackQueryHandler(fuel_lleno, pattern=r'^lleno_(yes|no)$')],
            FUEL_CONFIRM: [CallbackQueryHandler(fuel_confirm_yes, pattern=r'^confirm_yes$'),
                           CallbackQueryHandler(km_confirm_no, pattern=r'^confirm_no$')],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
        name="fuel_conversation",
        persistent=False,
    )

    expense_conv = ConversationHandler(
        entry_points=[CommandHandler('gasto', expense_start), MessageHandler(filters.Text(['💸 /gasto']), expense_start)],
        states={
            CAR_SELECT: [CallbackQueryHandler(expense_car, pattern=r'^car_\d+$')],
            EXPENSE_CONCEPT: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_concept),
                              CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            EXPENSE_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, expense_cost),
                           CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            EXPENSE_CAT: [CallbackQueryHandler(expense_cat, pattern=r'^cat_\w+$')],
            EXPENSE_CONFIRM: [CallbackQueryHandler(expense_confirm_yes, pattern=r'^confirm_yes$'),
                              CallbackQueryHandler(km_confirm_no, pattern=r'^confirm_no$')],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
        name="expense_conversation",
        persistent=False,
    )

    maint_conv = ConversationHandler(
        entry_points=[CommandHandler('mantenimiento', maint_start), MessageHandler(filters.Text(['🛠 /mantenimiento']), maint_start)],
        states={
            CAR_SELECT: [CallbackQueryHandler(maint_car, pattern=r'^car_\d+$')],
            MAINT_ACTION: [CallbackQueryHandler(maint_action, pattern=r'^maint_\w+$'),
                           CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            MAINT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, maint_name),
                CallbackQueryHandler(cancel_cb, pattern=r'^cancel$'),
            ],
            MAINT_INTERVAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, maint_interval),
                CallbackQueryHandler(cancel_cb, pattern=r'^cancel$'),
            ],
            MAINT_ITEM_SELECT: [CallbackQueryHandler(maint_item_select, pattern=r'^mitem_\d+_\w+$'),
                                CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
            MAINT_DEL_CONFIRM: [CallbackQueryHandler(maint_del_confirm, pattern=r'^maint_del_(yes|no)$')],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
        name="maint_conversation",
        persistent=False,
    )

    check_conv = ConversationHandler(
        entry_points=[CommandHandler('check', check_start), MessageHandler(filters.Text(['📋 /check']), check_start)],
        states={
            CHECK_CAR_SELECT: [CallbackQueryHandler(check_car, pattern=r'^car_\d+$')],
        },
        fallbacks=[CommandHandler('cancel', cancel),
                   CallbackQueryHandler(cancel_cb, pattern=r'^cancel$')],
        name="check_conversation",
        persistent=False,
    )

    return [km_conv, fuel_conv, expense_conv, maint_conv, check_conv,
            CommandHandler('start', start),
            CommandHandler('menu', menu),
            CommandHandler('alertas', alertas),
            CommandHandler('cancel', cancel),
            MessageHandler(filters.Text(['🔔 /alertas']), alertas),
            MessageHandler(filters.Text(['🏠 Menu']), menu)]

def main():
    token = TOKEN or os.environ.get('BOT_TOKEN') or get_setting('telegram_token')
    if not token:
        logger.error("Token de Telegram no configurado (env, DB ni settings)")
        return

    async def set_commands(app):
        await app.bot.set_my_commands([
            BotCommand("start", "Bienvenida y comandos"),
            BotCommand("menu", "Mostrar menu de botones"),
            BotCommand("km", "Registrar viaje"),
            BotCommand("repostar", "Registrar repostaje"),
            BotCommand("gasto", "Registrar gasto"),
            BotCommand("mantenimiento", "Items de mantenimiento"),
            BotCommand("check", "Resumen del coche"),
            BotCommand("alertas", "Alertas de todos los coches"),
            BotCommand("cancel", "Cancelar operacion"),
        ])

    app = Application.builder().token(token).post_init(set_commands).build()

    ids = allowed_user_ids()
    if ids:
        logger.info("Bot iniciado. Lista blanca: %s", sorted(ids))
    else:
        logger.warning("Bot iniciado SIN lista blanca: cualquier usuario puede "
                       "usarlo. Define TELEGRAM_ALLOWED_USER_IDS o el ajuste "
                       "'telegram_allowed_ids' y reinicia.")

    app.add_handler(TypeHandler(Update, _auth_guard), group=-1)
    for h in get_handlers():
        app.add_handler(h)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
