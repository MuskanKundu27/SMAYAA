import { describe, expect, it } from 'vitest'

import { menuFor, roleLabel } from './navigation'

const labels = (permissions: string[]) => menuFor(permissions).map((item) => item.label)

describe('menuFor', () => {
  it('gives an operator only the modules', () => {
    const operator = ['plants.read', 'readings.read', 'readings.write', 'modules.view', 'alerts.view']
    expect(labels(operator)).toEqual(['Water Chemistry', 'Filter', 'Thermal'])
  })

  it('gives a manager modules, limits and users but no company administration', () => {
    const manager = ['modules.view', 'limits.read', 'limits.write', 'users.read', 'users.manage:operator']
    expect(labels(manager)).toEqual(['Water Chemistry', 'Filter', 'Thermal', 'Limits', 'Users'])
  })

  it('gives a super admin administration only, never modules', () => {
    const superAdmin = ['companies.read', 'companies.manage', 'users.read', 'config.manage', 'audit.read']
    expect(labels(superAdmin)).toEqual(['Users', 'Companies', 'Configuration', 'Audit log'])
  })

  it('shows nothing without permissions', () => {
    expect(menuFor([])).toEqual([])
  })
})

describe('roleLabel', () => {
  it('translates known roles and passes unknown ones through', () => {
    expect(roleLabel('company_admin')).toBe('Company admin')
    expect(roleLabel('custom_role')).toBe('custom_role')
  })
})
