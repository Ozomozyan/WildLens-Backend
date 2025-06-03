/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "sans-serif"],
      },
      colors: {
        primary:  "#1F6832",   // deep forest green
        accent:   "#F0B429",   // sunlight gold
        gray900:  "#1A1A1A",
        gray100:  "#F5F5F5",
      },
      backgroundImage: {
        "page": "url('/src/assets/bg.jpg')",
      },
    },
  },
  plugins: [],
};
