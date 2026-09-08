-- Coordenadas desde Zenput /api/v3/locations para sucursales sin lat/lon (2026-09-08)
BEGIN;
UPDATE sucursales SET latitud=25.7522964, longitud=-100.1985347 WHERE zenput_location_id='2247034' AND (latitud IS NULL OR longitud IS NULL); -- 35 - Apodaca
UPDATE sucursales SET latitud=27.5141468, longitud=-99.5619493 WHERE zenput_location_id='2253476' AND (latitud IS NULL OR longitud IS NULL); -- 82 - Aeropuerto Nuevo Laredo
UPDATE sucursales SET latitud=25.7852038, longitud=-100.2805105 WHERE zenput_location_id='2260766' AND (latitud IS NULL OR longitud IS NULL); -- 83 - Cerradas de Anahuac
UPDATE sucursales SET latitud=25.8770507, longitud=-100.2291725 WHERE zenput_location_id='2260636' AND (latitud IS NULL OR longitud IS NULL); -- 84 - Aeropuerto del Norte
UPDATE sucursales SET latitud=25.7424654, longitud=-100.262608 WHERE zenput_location_id='2260765' AND (latitud IS NULL OR longitud IS NULL); -- 85 - Diego Diaz
UPDATE sucursales SET latitud=25.69489, longitud=-100.173324 WHERE zenput_location_id='2261286' AND (latitud IS NULL OR longitud IS NULL); -- 86 - Miguel de la Madrid
COMMIT;
