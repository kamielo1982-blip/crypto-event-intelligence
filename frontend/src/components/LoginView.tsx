import { FormEvent, useState } from "react";
import { Lock, LogIn } from "lucide-react";
import { login } from "../lib/api";

type Props = {
  onAuthenticated: (username: string) => void;
};

export function LoginView({ onAuthenticated }: Props) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const user = await login(username, password);
      onAuthenticated(user.username);
    } catch (err) {
      setError(err instanceof Error ? err.message : "로그인 실패");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <form className="w-full max-w-sm rounded border border-line bg-white p-5 shadow-sm" onSubmit={handleSubmit}>
        <div className="mb-5 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded bg-ink text-white">
            <Lock className="h-4 w-4" />
          </div>
          <div>
            <h1 className="text-lg font-semibold tracking-normal text-ink">Crypto Event Intelligence</h1>
            <p className="text-sm text-muted">Private admin dashboard</p>
          </div>
        </div>
        <label className="mb-3 block">
          <span className="mb-1 block text-sm font-medium text-ink">Username</span>
          <input
            className="h-10 w-full rounded border border-line px-3 text-sm outline-none focus:border-ink"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            autoComplete="username"
          />
        </label>
        <label className="mb-4 block">
          <span className="mb-1 block text-sm font-medium text-ink">Password</span>
          <input
            className="h-10 w-full rounded border border-line px-3 text-sm outline-none focus:border-ink"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            type="password"
            autoComplete="current-password"
          />
        </label>
        {error && <p className="mb-3 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-danger">{error}</p>}
        <button
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded bg-ink px-3 text-sm font-medium text-white disabled:opacity-60"
          disabled={isSubmitting}
        >
          <LogIn className="h-4 w-4" />
          로그인
        </button>
      </form>
    </main>
  );
}
