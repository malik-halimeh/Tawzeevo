// Development-only entry: deliberately absent from index.html and Vite build inputs.
import { createRoot } from "react-dom/client";
import { Icon, type IconName } from "./components/Icon";
import { PATHS } from "./components/iconGeometry";
import "./styles.css";
import "./map.css";

const names = Object.keys(PATHS) as IconName[];
const surfaces = [
  ["white", "White"], ["dark", "Dark · #1b1f24"],
  ["silver", "Silver bar · muted icons"], ["active", "Active · steel blue"],
] as const;

createRoot(document.getElementById("root")!).render(
  <div className="sheet">
    {surfaces.map(([className, label]) => <section className={className} key={className}>
      <h2>{label}</h2>
      <table>
        <thead><tr><th scope="col">Icon</th>{[17, 21, 48].map((size) => <th key={size} scope="col">{size}px</th>)}</tr></thead>
        <tbody>{names.map((name) => <tr key={name}>
          <th scope="row">{name}</th>
          {[17, 21, 48].map((size) => <td key={size}><span className="sample"><Icon name={name} small={size === 17} style={{ width: size, height: size }} /></span></td>)}
        </tr>)}</tbody>
      </table>
    </section>)}
  </div>,
);
