// Shapes returned by the API (see the API's /api/v1/docs for the full schema).

export interface MePlant {
  id: string
  name: string
  location: string
}

export interface Me {
  id: string
  username: string
  full_name: string
  roles: string[]
  permissions: string[]
  company: { id: string; name: string } | null
  plants: MePlant[]
}
