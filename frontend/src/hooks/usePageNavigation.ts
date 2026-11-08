import { useCallback, useEffect, useState } from 'react';

export type Page = 'selection' | 'results' | 'demo';
const readPage = (): Page => {
  const hash = window.location.hash.slice(1);
  return hash === 'results' || hash === 'demo' ? hash : 'selection';
};

export function usePageNavigation() {
  const [page, setPage] = useState<Page>(readPage);
  useEffect(() => {
    const sync = () => setPage(readPage());
    window.addEventListener('hashchange', sync);
    return () => window.removeEventListener('hashchange', sync);
  }, []);
  const navigate = useCallback((next: Page) => {
    setPage(next);
    if (window.location.hash !== `#${next}`) window.location.hash = next;
    window.scrollTo({ top: 0 });
  }, []);
  return { page, navigate };
}
