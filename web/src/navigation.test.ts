import { describe, expect, it } from 'vitest'

import { menuFor, roleLabel } from './navigation'

const labels = (permissions: string[]) => menuFor(permissions).map((item) => item.label)

// Module entries (Water Chemistry, Filter, Thermal) come from the API per plant, not from this
// static menu, so they never appear here.
describe('menuFor', () => {
  it('gives an operator no fixed pages (only API modules)', () => {
    const operator = ['plants.read', 'readings.read', 'readings.write', 'modules.view', 'alerts.view']
    expect(labels(operator)).toEqual([])
  })

  it('gives a manager limits and users but no company administration', () => {
    const manager = ['modules.view', 'limits.read', 'limits.write', 'users.read', 'users.manage:operator']
    expect(labels(manager)).toEqual(['Limits', 'Users'])
  })

  it('gives a super admin administration pages', () => {
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
