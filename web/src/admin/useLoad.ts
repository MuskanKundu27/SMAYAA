import { useCallback, useEffect, useState } from 'react'

import { ApiError } from '../api/client'

/** A readable message for any error thrown by an API call (including field details). */
export function errorMessage(err: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (!(err instanceof ApiError)) return fallback
  const details = err.details.map((d) => (d.field ? `${d.field}: ${d.message}` : d.message))
  return details.length > 0 ? `${err.message} ${details.join(' ')}` : err.message
}

export interface Loaded<T> {
  data: T | null
  error: string | null
  /** Load again (after a change). Keeps showing the old data until the new data arrives. */
  reload: () => void
}

/** Loads data when the component appears and whenever `deps` change. */
export function useLoad<T>(load: () => Promise<T>, deps: readonly unknown[]): Loaded<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [round, setRound] = useState(0)

  useEffect(() => {
    let cancelled = false
    load()
      .then((result) => {
        if (!cancelled) {
          setData(result)
          setError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(errorMessage(err, 'Could not load the data.'))
      })
    return () => {
      cancelled = true
    }
    // `load` is a new function on every render; `deps` says when to load again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, round])

  const reload = useCallback(() => setRound((r) => r + 1), [])
  return { data, error, reload }
}
