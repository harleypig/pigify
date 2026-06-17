import { BRAND } from "../lib/brand";
import "./Brand.css";

interface BrandProps {
  /** Which surface's size/treatment applies (drives the CSS class set). */
  surface: "login" | "header";
  /** id for the named element, so a container can `aria-labelledby` it. */
  wordmarkId?: string;
  /** Login-only: tint the logo's halo red on an auth error. */
  error?: boolean;
}

// Per-surface class sets. The shared <Brand> renders one structure; each
// surface keeps its own classes so its existing size/shadow CSS still applies
// (per the design: same structure everywhere, only the overall size differs).
const CLASSES = {
  login: {
    wrap: "console__lockup",
    logo: "console__logo",
    word: "console__wordmark",
  },
  header: {
    wrap: "app-brand",
    logo: "app-brand__logo",
    word: "app-brand__word",
  },
} as const;

/**
 * The brand mark — logo and/or wordmark — driven by the owner's `BRAND`
 * config (mode + layout). Replaces the duplicated lockups in Login/App.
 *
 * Modes: `lockup` shows both; `wordmark` shows text only; `image` shows the
 * logotype alone (its `alt` carries the name). `layout` flows the lockup via
 * `data-brand-layout` (see Brand.css).
 */
export function Brand({ surface, wordmarkId, error = false }: BrandProps) {
  const cls = CLASSES[surface];
  const showImage = BRAND.mode !== "wordmark";
  const showWord = BRAND.mode !== "image";

  return (
    <div className={cls.wrap} data-brand-layout={BRAND.layout}>
      {showImage && (
        <img
          className={`${cls.logo}${error ? " is-error" : ""}`}
          src={BRAND.image}
          // The wordmark names the lockup; in image-only mode the image must
          // carry the name itself.
          alt={showWord ? "" : BRAND.wordmark}
          id={showWord ? undefined : wordmarkId}
        />
      )}
      {showWord && (
        <h1 className={cls.word} id={wordmarkId}>
          {BRAND.wordmark}
        </h1>
      )}
    </div>
  );
}
