// The menu. Each entry is shown only if the user has its permission (from GET /me).
// Hiding a menu entry is a convenience, not security: the API checks every request itself.

export interface MenuItem {
  path: string
  label: string
  permission: string
  section: 'Plant' | 'Administration'
}

// Fixed pages. The module entries (Water Chemistry, Filter, Thermal, ...) are not listed here:
// they come from the API per plant, because modules are configuration data (see AppLayout).
export const MENU: MenuItem[] = [
  { path: '/limits', label: 'Limits', permission: 'limits.read', section: 'Plant' },
  {
    path: '/operator-profiles',
    label: 'Operator profiles',
    permission: 'operator_profiles.manage',
    section: 'Plant',
  },
  { path: '/users', label: 'Users', permission: 'users.read', section: 'Administration' },
  { path: '/plants', label: 'Plants', permission: 'plants.manage', section: 'Administration' },
  { path: '/companies', label: 'Companies', permission: 'companies.read', section: 'Administration' },
  { path: '/configuration', label: 'Configuration', permission: 'config.manage', section: 'Administration' },
  { path: '/audit-log', label: 'Audit log', permission: 'audit.read', section: 'Administration' },
]

export function menuFor(permissions: readonly string[]): MenuItem[] {
  const granted = new Set(permissions)
  return MENU.filter((item) => granted.has(item.permission))
}

const ROLE_LABELS: Record<string, string> = {
  super_admin: 'Super admin',
  company_admin: 'Company admin',
  manager: 'Manager',
  operator: 'Operator',
}

export function roleLabel(roleKey: string): string {
  return ROLE_LABELS[roleKey] ?? roleKey
}

const MANAGE_PREFIX = 'users.manage:'

/** Roles this user may create and deactivate (from `users.manage:<role>` permissions). */
export function manageableRoles(permissions: readonly string[]): string[] {
  return permissions.filter((p) => p.startsWith(MANAGE_PREFIX)).map((p) => p.slice(MANAGE_PREFIX.length))
}

/** Whether a new user of this role belongs to a company (picked by a platform admin) or a plant.
 *  The API decides from the role's scope; this only chooses which field the form shows. */
export function roleNeedsPlant(roleKey: string): boolean {
  return roleKey !== 'company_admin'
}
