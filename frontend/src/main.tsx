import React from "react";
import ReactDOM from "react-dom/client";
import { CssBaseline, ThemeProvider, alpha, createTheme } from "@mui/material";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import App from "./views/App";

const theme = createTheme({
  palette: {
    mode: "light",
    primary: { main: "#2563eb", dark: "#1e3a8a" },
    secondary: { main: "#0f766e" },
    background: { default: "#f5f7fb", paper: "#ffffff" },
    text: { primary: "#0f172a", secondary: "#475569" }
  },
  typography: {
    fontFamily: "\"Inter\", \"SF Pro Text\", \"Segoe UI\", \"Roboto\", \"Helvetica\", \"Arial\", sans-serif",
    h3: { fontWeight: 700, letterSpacing: "-0.02em" },
    h4: { fontWeight: 700, letterSpacing: "-0.015em" },
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600 },
    subtitle1: { fontWeight: 500 }
  },
  shape: {
    borderRadius: 16
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        "*, *::before, *::after": {
          boxSizing: "border-box"
        },
        body: {
          margin: 0,
          background: "linear-gradient(180deg, #f8fafc 0%, #eef2ff 55%, #f5f7fb 100%)",
          color: "#0f172a",
          WebkitFontSmoothing: "antialiased",
          MozOsxFontSmoothing: "grayscale"
        },
        "#root": {
          minHeight: "100vh"
        }
      }
    },
    MuiTypography: {
      styleOverrides: {
        root: {
          overflowWrap: "anywhere"
        }
      }
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          backgroundColor: alpha("#0f172a", 0.85),
          backdropFilter: "blur(14px)",
          boxShadow: "0 10px 30px rgba(15, 23, 42, 0.18)"
        }
      }
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderRight: "1px solid rgba(148, 163, 184, 0.2)",
          backgroundColor: "#0b1120",
          color: "#e2e8f0"
        }
      }
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 14,
          margin: "4px 12px",
          paddingTop: 10,
          paddingBottom: 10,
          "&.Mui-selected": {
            backgroundColor: alpha("#2563eb", 0.2),
            color: "#e2e8f0"
          },
          "&.Mui-selected:hover": {
            backgroundColor: alpha("#2563eb", 0.28)
          }
        }
      }
    },
    MuiCard: {
      styleOverrides: {
        root: {
          border: "1px solid rgba(148, 163, 184, 0.24)",
          borderRadius: 20,
          boxShadow: "0 18px 40px rgba(15, 23, 42, 0.08)"
        }
      }
    },
    MuiCardContent: {
      styleOverrides: {
        root: {
          padding: 24
        }
      }
    },
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 999,
          textTransform: "none",
          fontWeight: 600,
          paddingInline: 20
        },
        contained: {
          boxShadow: "0 12px 22px rgba(37, 99, 235, 0.28)"
        },
        outlined: {
          borderColor: alpha("#2563eb", 0.4)
        }
      }
    },
    MuiTextField: {
      defaultProps: {
        variant: "outlined",
        size: "small"
      }
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          backgroundColor: "#f8fafc",
          borderRadius: 12
        }
      }
    },
    MuiChip: {
      styleOverrides: {
        root: {
          borderRadius: 999
        }
      }
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: "rgba(148, 163, 184, 0.3)"
        }
      }
    }
  }
});

const queryClient = new QueryClient();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </QueryClientProvider>
    </ThemeProvider>
  </React.StrictMode>
);
