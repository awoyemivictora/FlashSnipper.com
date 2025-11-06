// module.exports = {
//   content: ["./src/**/*.{js,ts,jsx,tsx,html,mdx}"],
//   darkMode: "class",
//   theme: {
//     extend: {
//       colors: {
//         background: {
//           primary: "var(--bg-primary)",
//           secondary: "var(--bg-secondary)",
//           overlay: "var(--bg-overlay)",
//           success: "var(--bg-success)",
//           dark1: "var(--bg-dark-1)",
//           dark2: "var(--bg-dark-2)",
//           accent: "var(--bg-accent)",
//           warningLight: "var(--bg-warning-light)",
//           errorLight: "var(--bg-error-light)",
//           white: "var(--bg-white)"
//         },
//         text: {
//           success: "var(--text-success)",
//           primary: "var(--text-primary)",
//           muted: "var(--text-muted)",
//           secondary: "var(--text-secondary)",
//           warning: "var(--text-warning)",
//           light: "var(--text-light)",
//           white: "var(--text-white)",
//           whiteTransparent: "var(--text-white-transparent)"
//         }
//       },
//       animation: {
//         'float': 'float 6s ease-in-out infinite',
//         'float-slow': 'float 8s ease-in-out infinite',
//       },
//       keyframes: {
//         float: {
//           '0%, 100%': { transform: 'translateY(0)' },
//           '50%': { transform: 'translateY(-20px)' },
//         }
//       }
//     }
//   },
//   plugins: []
// };







module.exports = {
  content: ["./src/**/*.{js,ts,jsx,tsx,html,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['Nunito', 'sans-serif'],
        nunito: ['Nunito', 'sans-serif'],
      },
      colors: {
        background: {
          primary: "var(--bg-primary)",
          secondary: "var(--bg-secondary)",
          overlay: "var(--bg-overlay)",
          success: "var(--bg-success)",
          dark1: "var(--bg-dark-1)",
          dark2: "var(--bg-dark-2)",
          accent: "var(--bg-accent)",
          warningLight: "var(--bg-warning-light)",
          errorLight: "var(--bg-error-light)",
          white: "var(--bg-white)"
        },
        text: {
          success: "var(--text-success)",
          primary: "var(--text-primary)",
          muted: "var(--text-muted)",
          secondary: "var(--text-secondary)",
          warning: "var(--text-warning)",
          light: "var(--text-light)",
          white: "var(--text-white)",
          whiteTransparent: "var(--text-white-transparent)"
        }
      },
      animation: {
        'float': 'float 6s ease-in-out infinite',
        'float-slow': 'float 8s ease-in-out infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-20px)' },
        }
      }
    }
  },
  plugins: []
};

