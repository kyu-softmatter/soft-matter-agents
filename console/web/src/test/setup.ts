import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// The shared PC is often loaded (many sessions, a fresh npm ci): give waits for
// lazy screens and fake-socket updates room. A wait still ends as soon as its
// condition holds, so this costs nothing when the machine is fast.
configure({ asyncUtilTimeout: 10_000 });

afterEach(() => {
  cleanup();
  window.location.hash = "";
});
