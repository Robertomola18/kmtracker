# Security Policy

## Alcance

KMtracker está pensado para **uso personal/privado**. Expón el puerto web solo
en tu red local o detrás de un proxy con TLS o una VPN. El acceso web usa una
**única contraseña** (`KMTRACKER_PASSWORD`): usa una contraseña robusta y no
publiques el servicio directamente en Internet sin TLS.

El bot de Telegram **no** aplica autenticación por sí mismo más allá de la lista
blanca: configura siempre `TELEGRAM_ALLOWED_USER_IDS` (o el ajuste
`telegram_allowed_ids`), o cualquiera que encuentre el bot podrá leer y
modificar los datos.

## Reportar una vulnerabilidad

Si encuentras un problema de seguridad, abre un aviso privado (Security Advisory)
en el repositorio en lugar de un issue público, indicando pasos para
reproducirlo. Se agradece el aviso responsable.
