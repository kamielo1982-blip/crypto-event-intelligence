import { useEffect, useState } from "react";
import { Activity, BarChart3, FileText, HeartPulse, LogOut, RefreshCw, Rss } from "lucide-react";
import { getAssets, logout, me } from "./lib/api";
import type { Asset } from "./types";
import { CoinIntelligence } from "./components/CoinIntelligence";
import { DataHealth } from "./components/DataHealth";
import { EventFeed } from "./components/EventFeed";
import { LoginView } from "./components/LoginView";
import { MarketBrief } from "./components/MarketBrief";

type View = "brief" | "coin" | "events" | "health";

const navItems = [
  { key: "brief" as View, label: "Market Brief", icon: BarChart3 },
  { key: "coin" as View, label: "Coin Intelligence", icon: Activity },
  { key: "events" as View, label: "Event & Signal Feed", icon: Rss },
  { key: "health" as View, label: "Data Health", icon: HeartPulse }
];

function App() {
  const [username, setUsername] = useState<string | null>(null);
  const [isBooting, setIsBooting] = useState(true);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [activeView, setActiveView] = useState<View>("brief");
  const [selectedSymbol, setSelectedSymbol] = useState("BTC");

  useEffect(() => {
    me()
      .then((user) => {
        setUsername(user.username);
        return getAssets();
      })
      .then((rows) => {
        setAssets(rows);
        const firstInvestable = rows.find((asset) => asset.group === "investable");
        if (firstInvestable) setSelectedSymbol(firstInvestable.symbol);
      })
      .catch(() => setUsername(null))
      .finally(() => setIsBooting(false));
  }, []);

  async function handleLogout() {
    await logout();
    setUsername(null);
  }

  function handleAuthenticated(user: string) {
    setUsername(user);
    getAssets().then((rows) => {
      setAssets(rows);
      const firstInvestable = rows.find((asset) => asset.group === "investable");
      if (firstInvestable) setSelectedSymbol(firstInvestable.symbol);
    });
  }

  if (isBooting) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-100 text-sm text-muted">
        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
        세션 확인 중
      </div>
    );
  }

  if (!username) {
    return <LoginView onAuthenticated={handleAuthenticated} />;
  }

  const investableAssets = assets.filter((asset) => asset.group === "investable");

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="sticky top-0 z-10 border-b border-line bg-white">
        <div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-3 px-4 py-3 lg:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded bg-ink text-white">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-base font-semibold tracking-normal text-ink">Crypto Event Intelligence</h1>
              <p className="truncate text-xs text-muted">KST 09:00, 15:00, 21:00 snapshot MVP</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="hidden text-sm text-muted sm:inline">{username}</span>
            <button
              className="inline-flex h-9 items-center gap-2 rounded border border-line bg-white px-3 text-sm text-ink hover:bg-slate-50"
              onClick={handleLogout}
              title="로그아웃"
            >
              <LogOut className="h-4 w-4" />
              로그아웃
            </button>
          </div>
        </div>
        <nav className="mx-auto flex max-w-[1500px] gap-1 overflow-x-auto px-4 pb-3 lg:px-6">
          {navItems.map((item) => {
            const Icon = item.icon;
            const active = activeView === item.key;
            return (
              <button
                key={item.key}
                className={`inline-flex h-9 shrink-0 items-center gap-2 rounded border px-3 text-sm ${
                  active ? "border-ink bg-ink text-white" : "border-line bg-white text-ink hover:bg-slate-50"
                }`}
                onClick={() => setActiveView(item.key)}
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </button>
            );
          })}
        </nav>
      </header>

      <main className="mx-auto max-w-[1500px] px-4 py-5 lg:px-6">
        {activeView === "brief" && (
          <MarketBrief
            onSelectAsset={(symbol) => {
              setSelectedSymbol(symbol);
              setActiveView("coin");
            }}
          />
        )}
        {activeView === "coin" && (
          <CoinIntelligence assets={investableAssets} selectedSymbol={selectedSymbol} onSelectSymbol={setSelectedSymbol} />
        )}
        {activeView === "events" && <EventFeed assets={investableAssets} />}
        {activeView === "health" && <DataHealth />}
      </main>
    </div>
  );
}

export default App;
