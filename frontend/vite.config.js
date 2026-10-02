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

    proxy: {
      "/session": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/message": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/menu": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/cart": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/order": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/meal": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/stt": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },

      "/tts": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});