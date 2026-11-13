"use client";

import { useEffect, useState } from "react";

export function useTimedNotice(timeoutMs = 2200) {
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!notice) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setNotice(null);
    }, timeoutMs);

    return () => {
      window.clearTimeout(timeout);
    };
  }, [notice, timeoutMs]);

  return [notice, setNotice] as const;
}
