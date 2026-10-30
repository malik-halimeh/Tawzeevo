import { useId, type SVGProps } from "react";
import { PATHS, type IconGeometry } from "./iconGeometry";
import "./icons.css";

export type IconName = keyof typeof PATHS;

/** Decorative local solids. Icon-only controls must still supply their own accessible name. */
export function Icon({ name, small = false, className = "", ...rest }: { name: IconName; small?: boolean } & SVGProps<SVGSVGElement>) {
  const maskId = `icon-${useId()}`;
  const { body, cutout, strokes }: IconGeometry = PATHS[name];
  return (
    <svg aria-hidden="true" className={`icon icon-solid${small ? " icon-small" : ""}${className ? ` ${className}` : ""}`} focusable="false" viewBox="0 0 24 24" {...rest}>
      {cutout && <defs>
        <mask id={maskId} className="icon-mask" maskUnits="userSpaceOnUse" maskContentUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">
          <rect x="0" y="0" width="24" height="24" fill="#fff" />
          <g fill="none" stroke="#000" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{cutout}</g>
        </mask>
      </defs>}
      {body && <g mask={cutout ? `url(#${maskId})` : undefined}>{body}</g>}
      {strokes && <g className="icon-strokes">{strokes}</g>}
    </svg>
  );
}

/** A directional arrow that mirrors in right-to-left layouts (product photos and numbers never do). */
export function Arrow({ back = false, small = false }: { back?: boolean; small?: boolean }) {
  return <span className="directional"><Icon name={back ? "back" : "arrow"} small={small} /></span>;
}
