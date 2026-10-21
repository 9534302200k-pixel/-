import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  define: { "import.meta.env.VITE_VISUAL_DEMO": JSON.stringify("true") },
  build: {
    outDir: "visual-dist",
    rollupOptions: { output: { inlineDynamicImports: true } },
    cssCodeSplit: false,
  },
});
