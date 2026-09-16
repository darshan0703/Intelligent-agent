import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { viteStaticCopy } from "vite-plugin-static-copy";

export default defineConfig({
  plugins: [
    react(),

    viteStaticCopy({
      targets: [
        {
          src: "node_modules/onnxruntime-web/dist/*",
          dest: "vad",
        },
        {
          src: "node_modules/@ricky0123/vad-web/dist/*",
          dest: "vad",
        },
      ],
    }),
  ],

  server: {
    allowedHosts: [
      "plunging-marital-unsafe.ngrok-free.dev",
    ],
  },
});