// The 3D trajectory viewer (T-022). The simulation screen's 2D/3D switch lazy-loads this module
// and uses the named export, so `three` is fetched only when the 3D view is opened.
export { Viewer3D } from "./Viewer3D";
export type { CreateRenderer, Renderer, Viewer3DProps } from "./Viewer3D";
