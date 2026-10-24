import { NotBuilt } from "../../app/NotBuilt";

/** The library area, until its own card builds it (console card 008). Requests nothing. */
export default function LibraryScreen() {
  return (
    <NotBuilt
      title="Library"
      shows="Send the librarian a request. The librarian decides, and nothing is ever erased."
    />
  );
}
