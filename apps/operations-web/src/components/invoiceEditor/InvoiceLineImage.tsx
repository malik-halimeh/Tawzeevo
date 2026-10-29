import { useEffect, useState } from "react";

import { apiBlobRequest } from "../../api/client";

export function InvoiceLineImage({ url, name }: { url: string; name: string }) {
  const [source, setSource] = useState<string>();

  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    void apiBlobRequest(url)
      .then((blob) => {
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource(objectUrl);
      })
      .catch(() => setSource(undefined));
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);

  return source ? <img alt={name} className="invoice-line-image" src={source} /> : null;
}
