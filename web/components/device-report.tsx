import { provenanceRows } from "../lib/device-reports";
import type { Photo } from "../lib/types";

/**
 * Where a device report came from: the submitting device, the app and model that screened
 * it, the consent and licence chosen on the phone, and the exact point it was taken.
 */
export default function DeviceReport({ photo }: { photo: Photo }) {
  if (!photo.device) return null;
  return (
    <section className="device-report" aria-labelledby="device-report-heading">
      <h3 id="device-report-heading">Device report</h3>
      <p>
        Approved and sent from a phone. The suggestion came from on-device screening; the location
        is where the phone was, not the plant.
      </p>
      <dl>
        {provenanceRows(photo, photo.device).map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
