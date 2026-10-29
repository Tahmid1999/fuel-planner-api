import { useEffect, useState } from "react";

// True once `active` has stayed true for `ms`; used to explain a slow first
// request while the free API host wakes up.
export function useSlow(active: boolean, ms = 5000) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    setSlow(false);
    if (!active) return;
    const t = setTimeout(() => setSlow(true), ms);
    return () => clearTimeout(t);
  }, [active, ms]);
  return slow;
}
