// The menu. Each entry is shown only if the user has its permission (from GET /me).
// Hiding a menu entry is a convenience, not security: the API checks every request itself.

export interface MenuItem {
  path: string
  label: string
  permission: string
  section: 'Modules' | 'Plant' | 'Administration'
  /** Which build step delivers the real page (shown on the placeholder until then). */
  comingIn: string
}

// TEMPORARY: the three module entries are listed here only until Step 4, when the list of
// modules comes from the API (modules are configuration data per company, not code).
export const MENU: MenuItem[] = [
  { path: '/water-chemistry', label: 'Water Chemistry', permission: 'modules.view', section: 'Modules', comingIn: 'Step 4' },
  { path: '/filter', label: 'Filter', permission: 'modules.view', section: 'Modules', comingIn: 'Step 4' },
  { path: '/thermal', label: 'Thermal', permission: 'modules.view', section: 'Modules', comingIn: 'Step 4' },
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
