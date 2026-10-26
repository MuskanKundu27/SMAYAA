import { useEffect } from 'react'

/** Scrolls the page to the top when the calling component appears, e.g. an editor opened
 * from a row far down a long list, so the form is in view. */
export function useScrollToTop(): void {
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }, [])
}
