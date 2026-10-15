-- Ejecutar en la base ingresos de MySQL 8.4.
SELECT VERSION();
SELECT id, code, name, is_active FROM roles ORDER BY id;
SELECT id, code, name, is_active FROM permissions ORDER BY id;
SELECT r.code AS rol, p.code AS permiso, rp.is_active
FROM role_permissions rp
JOIN roles r ON r.id = rp.role_id
JOIN permissions p ON p.id = rp.permission_id
ORDER BY r.id, p.id;

-- Matriz comparativa: la carga inicial produce 26 relaciones activas.
SELECT p.code AS permiso,
 MAX(CASE WHEN r.code='ADMINISTRADOR' AND rp.is_active=1 THEN 1 ELSE 0 END) AS ADMINISTRADOR,
 MAX(CASE WHEN r.code='CONTADOR' AND rp.is_active=1 THEN 1 ELSE 0 END) AS CONTADOR,
 MAX(CASE WHEN r.code='CAPTURISTA' AND rp.is_active=1 THEN 1 ELSE 0 END) AS CAPTURISTA,
 MAX(CASE WHEN r.code='CONSULTA' AND rp.is_active=1 THEN 1 ELSE 0 END) AS CONSULTA
FROM permissions p LEFT JOIN role_permissions rp ON rp.permission_id=p.id
LEFT JOIN roles r ON r.id=rp.role_id GROUP BY p.id,p.code ORDER BY p.id;

-- Debe devolver cero filas: membresías activas sin exactamente un rol activo.
SELECT cu.id, COUNT(CASE WHEN cur.is_active=1 AND r.is_active=1 THEN 1 END) AS roles_activos
FROM company_users cu LEFT JOIN company_user_roles cur ON cur.company_user_id=cu.id
LEFT JOIN roles r ON r.id=cur.role_id WHERE cu.is_active=1
GROUP BY cu.id HAVING roles_activos <> 1;

SELECT cu.id, cu.company_id, cu.is_admin, r.code AS rol, cur.is_active
FROM company_users cu JOIN company_user_roles cur ON cur.company_user_id=cu.id
JOIN roles r ON r.id=cur.role_id ORDER BY cu.id,cur.id;

-- Ejecutar antes/después del rechazo de CONSULTA: el conteo no cambia.
SELECT COUNT(*) AS total_movimientos FROM transactions;
SELECT COUNT(*) AS total_roles FROM roles;
SELECT COUNT(*) AS total_permisos FROM permissions;
SELECT COUNT(*) AS total_relaciones FROM role_permissions;

-- Actividad 4: al cerrar, la matriz activa vuelve a las 26 parejas iniciales.
-- Las dos parejas de la demostración se conservan con is_active=0.
SELECT COUNT(*) AS relaciones_activas FROM role_permissions WHERE is_active=1;
SELECT r.code AS rol, p.code AS permiso, rp.id, rp.is_active
FROM role_permissions rp JOIN roles r ON r.id=rp.role_id
JOIN permissions p ON p.id=rp.permission_id
WHERE (r.code='CAPTURISTA' AND p.code='accounts.write')
   OR (r.code='CONSULTA' AND p.code='concepts.write')
ORDER BY r.code, p.code;
