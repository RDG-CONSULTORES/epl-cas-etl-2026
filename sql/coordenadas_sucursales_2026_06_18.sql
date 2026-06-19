-- Carga de coordenadas faltantes para sucursales que no aparecían en el mapa.
-- Detectado en el triple-check del 2026-06-18 (6 de 86 sucursales sin lat/long).
-- Coordenadas provistas por el usuario. Se identifican por `numero` (clave de
-- negocio estable entre staging y producción).
-- Aplicado primero en STAGING; aplicar en PROD cuando se apruebe.
-- Cubre las 6 sucursales que estaban sin coordenadas.

UPDATE sucursales SET latitud = 25.752511075181243, longitud = -100.19865560166494 WHERE numero = 35;  -- Apodaca
UPDATE sucursales SET latitud = 27.514209753605860, longitud =  -99.56307226441753 WHERE numero = 82;  -- Aeropuerto Nuevo Laredo
UPDATE sucursales SET latitud = 25.785663914621654, longitud = -100.28005289447808 WHERE numero = 83;  -- Cerradas de Anahuac
UPDATE sucursales SET latitud = 25.873991350822152, longitud = -100.22864182626080 WHERE numero = 84;  -- Aeropuerto del Norte
UPDATE sucursales SET latitud = 25.752639340451612, longitud = -100.25402613468229 WHERE numero = 85;  -- Diego Diaz
UPDATE sucursales SET latitud = 25.694986029391533, longitud = -100.17338557097243 WHERE numero = 86;  -- Miguel de la Madrid

-- Correcciones de coordenadas mal ubicadas (provistas por el usuario 2026-06-18).
UPDATE sucursales SET latitud = 25.592885852506583, longitud = -100.00160683772692 WHERE numero = 26;  -- Cadereyta
UPDATE sucursales SET latitud = 25.744332844388120, longitud = -100.30065889821458 WHERE numero =  9;  -- Anahuac
UPDATE sucursales SET latitud = 25.659053129298304, longitud = -100.35634853373679 WHERE numero = 38;  -- Gomez Morin
