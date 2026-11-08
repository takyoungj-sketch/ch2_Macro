// @ts-nocheck — React is supplied by the consuming frontend.
import { useEffect, useState } from "react";

const QUERY = "(max-width: 767px), (max-width: 1024px) and (max-height: 500px)";
export function useMobileScreen() {
  const [mobile, setMobile] = useState(() => window.matchMedia(QUERY).matches);
  useEffect(() => {
    const media = window.matchMedia(QUERY);
    const update = () => setMobile(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  return mobile;
}
