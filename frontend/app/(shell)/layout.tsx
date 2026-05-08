import type { ReactNode } from "react";

import { ShellChrome } from "@/components/shell/shell-chrome";
import { ShellProvider } from "@/components/shell/shell-context";

export default function ShellLayout({ children }: { children: ReactNode }) {
  return (
    <ShellProvider>
      <ShellChrome>{children}</ShellChrome>
    </ShellProvider>
  );
}
