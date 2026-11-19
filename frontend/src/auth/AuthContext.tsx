import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { AuthApi } from "../api/endpoints";
import { clearToken, getToken, setToken } from "../api/client";
import type { User } from "../api/types";

interface AuthContextValue {
  user: User | null;
  isLoading: boolean;
  registrationTutorialPending: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, fullName: string, password: string) => Promise<void>;
  consumeRegistrationTutorial: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [registrationTutorialPending, setRegistrationTutorialPending] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    AuthApi.me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setIsLoading(false));
  }, []);

  async function login(email: string, password: string) {
    const { access_token } = await AuthApi.login(email, password);
    setToken(access_token);
    const me = await AuthApi.me();
    setUser(me);
  }

  async function register(email: string, fullName: string, password: string) {
    await AuthApi.register(email, fullName, password);
    await login(email, password);
    setRegistrationTutorialPending(true);
  }

  function consumeRegistrationTutorial() {
    setRegistrationTutorialPending(false);
  }

  async function logout() {
    try {
      await AuthApi.logout();
    } finally {
      clearToken();
      setUser(null);
      setRegistrationTutorialPending(false);
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        registrationTutorialPending,
        login,
        register,
        consumeRegistrationTutorial,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within an AuthProvider");
  return context;
}
