# Accesibilidad de la interfaz

Referencia: WCAG 2.2 AA, https://www.w3.org/TR/WCAG22/.
Estos cambios no constituyen una declaración de conformidad ni una auditoría completa.

## Cambios
- Texto base relativo de 1rem y texto auxiliar de al menos .875rem en los componentes principales.
- Controles principales de 44px de altura; foco con borde oscuro y halo blanco.
- Bordes de campos contrastados y enlaces de contenido subrayados.
- Enlace para saltar al contenido y regiones de desplazamiento accesibles por teclado.
- Errores agrupados con enlaces a campos y ayudas vinculadas a su control.
- Reflujo de cabecera y tarjetas; tablas y Gantt conservan desplazamiento horizontal propio.
- Reloj integrado en la cabecera para evitar superponer controles al ampliar.
- Etiquetas de vencimiento en el Gantt, además del color.
- Restauración de foco al aplicar filtros; no reemplazar alertas que contienen el foco.
- El hub actualiza alertas automáticamente; el botón de pausa fue retirado por decisión de producto. Los estilos de movimiento reducido se conservan.
- Pausa TV detiene tanto la rotación como la actualización de datos.

## Comprobaciones realizadas
Suite Django: 78 pruebas aprobadas. Sin cambios de modelo ni migraciones.
Contraste calculado con luminancia relativa WCAG:
- Blanco / verde #15803d: 5.02:1.
- Texto #59675e / fondo #f4f6f4: 5.48:1.
- Blanco / rojo #dc2626: 4.83:1.
- Borde #65766a / blanco: 4.82:1.
- Negro / fondo del reloj #2fbd32: 8.45:1.

## Validación pendiente
El navegador no pudo conectar al servidor temporal local durante esta revisión.
Validar visualmente escritorio y 320 CSS px, zoom 200% y 400%, espaciado de texto
personalizado, navegación completa con Tab/Shift+Tab/Enter/Espacio y lector de pantalla
(por ejemplo NVDA). Revisar login, errores de formularios, perfil, hub, historial,
Gantt y TV. Ejecutar auditoría automatizada en navegador y revisión manual antes de
afirmar conformidad completa. Verificar que el foco se conserve después de filtros,
que no haya contenido cortado y revisar de nuevo los criterios relacionados con actualizaciones automáticas.
