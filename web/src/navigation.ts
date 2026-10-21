// The menu. Each entry is shown only if the user has its permission (from GET /me).
// Hiding a menu entry is a convenience, not security: the API checks every request itself.

export interface MenuItem {
  path: string
  label: string
  permission: string
  section: 'Plant' | 'Administration'
  /** Which build step delivers the real page (shown on the placeholder until then). */
  comingIn: string
}

// Fixed pages. The module entries (Water Chemistry, Filter, Thermal, ...) are not listed here:
// they come from the API per plant, because modules are configuration data (see AppLayout).
export const MENU: MenuItem[] = [
  { path: '/limits', label: 'Limits', permission: 'limits.read', section: 'Plant', comingIn: 'Step 5' },
  { path: '/users', label: 'Users', permission: 'users.read', section: 'Administration', comingIn: 'Step 5' },
  { path: '/plants', label: 'Plants', permission: 'plants.manage', section: 'Administration', comingIn: 'Step 5' },
  { path: '/companies', label: 'Companies', permission: 'companies.read', section: 'Administration', comingIn: 'Step 5' },
  { path: '/configuration', label: 'Configuration', permission: 'config.manage', section: 'Administration', comingIn: 'Step 5' },
  { path: '/audit-log', label: 'Audit log', permission: 'audit.read', section: 'Administration', comingIn: 'Step 5' },
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
