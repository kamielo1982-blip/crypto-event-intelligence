/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#15202b",
        muted: "#637083",
        panel: "#ffffff",
        line: "#d8dee8",
        accent: "#0f7b6c",
        warn: "#b06a00",
        danger: "#b42318"
      }
    }
  },
  plugins: []
};
