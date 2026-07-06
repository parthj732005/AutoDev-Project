import { useEffect, useState } from "react";
import { api } from "../services/api";

const PROVIDERS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "groq", label: "Groq (Free)" },
  { value: "huggingface", label: "HuggingFace" },
  { value: "ollama", label: "Ollama (Local • Slow on CPU)" },
];

export default function Settings() {
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getSettings().then(setSettings).catch((e) => setError(e.message));
  }, []);

  async function handleSave(e) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      await api.saveSettings(settings);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function set(key, value) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  if (!settings) {
    return (
      <div className="p-8 space-y-3 max-w-lg">
        {error ? (
          <>
            <p className="text-danger font-medium">Could not reach backend</p>
            <p className="text-slate-500 text-sm">{error}</p>
            <div className="card bg-warning/5 border-warning/20 text-xs text-slate-400 space-y-1">
              <p className="text-warning font-semibold mb-2">Start the backend first:</p>
              <p className="font-mono">cd backend</p>
              <p className="font-mono">pip install -r requirenments.txt</p>
              <p className="font-mono">uvicorn app.main:app --reload</p>
            </div>
          </>
        ) : (
          <p className="text-slate-500 text-sm">Loading settings...</p>
        )}
      </div>
    );
  }

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-xl font-bold text-slate-100 mb-1">Settings</h1>
      <p className="text-sm text-slate-500 mb-6">Configure your AI provider and output directory.</p>

      <form onSubmit={handleSave} className="space-y-6">
        {/* Provider */}
        <div className="card space-y-4">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest">
            AI Provider
          </h2>
          <div className="flex gap-3">
            {PROVIDERS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => set("provider", p.value)}
                className={`flex-1 py-2.5 rounded-lg border text-sm font-medium transition-colors ${
                  settings.provider === p.value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-slate-400 hover:border-slate-500"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {settings.provider === "openai" && (
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">OpenAI API Key</span>
                <input
                  type="password"
                  className="input"
                  value={settings.openai_api_key || ""}
                  onChange={(e) => set("openai_api_key", e.target.value)}
                  placeholder="sk-..."
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Model</span>
                <select
                  className="input"
                  value={settings.openai_model || "gpt-5.4-mini"}
                  onChange={(e) => set("openai_model", e.target.value)}
                >
                  <option value="gpt-5.4-mini">gpt-5.4-mini (recommended)</option>
                  <option value="gpt-5.5">gpt-5.5</option>
                  <option value="gpt-5.4">gpt-5.4</option>
                </select>
              </label>
            </div>
          )}

          {settings.provider === "anthropic" && (
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Anthropic API Key</span>
                <input
                  type="password"
                  className="input"
                  value={settings.anthropic_api_key || ""}
                  onChange={(e) => set("anthropic_api_key", e.target.value)}
                  placeholder="sk-ant-..."
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Model</span>
                <select
                  className="input"
                  value={settings.anthropic_model || "claude-sonnet-5"}
                  onChange={(e) => set("anthropic_model", e.target.value)}
                >
                  <option value="claude-sonnet-5">claude-sonnet-5 (recommended)</option>
                  <option value="claude-opus-4-8">claude-opus-4-8</option>
                  <option value="claude-haiku-4-5">claude-haiku-4-5</option>
                </select>
              </label>
            </div>
          )}

          {settings.provider === "groq" && (
            <div className="space-y-3">
              <div className="text-xs text-success bg-success/10 border border-success/20 rounded-lg px-3 py-2">
                Groq is free and very fast. Get your key at{" "}
                <span className="font-mono">console.groq.com</span>
              </div>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Groq API Key</span>
                <input
                  type="password"
                  className="input"
                  value={settings.groq_api_key || ""}
                  onChange={(e) => set("groq_api_key", e.target.value)}
                  placeholder="gsk_..."
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Model</span>
                <select
                  className="input"
                  value={settings.groq_model || "llama-3.3-70b-versatile"}
                  onChange={(e) => set("groq_model", e.target.value)}
                >
                  <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (recommended)</option>
                  <option value="openai/gpt-oss-120b">openai/gpt-oss-120b</option>
                  <option value="openai/gpt-oss-20b">openai/gpt-oss-20b</option>
                  <option value="llama-3.1-8b-instant">llama-3.1-8b-instant</option>
                </select>
              </label>
            </div>
          )}

          {settings.provider === "huggingface" && (
            <div className="space-y-3">
              <div className="text-xs text-primary bg-primary/10 border border-primary/20 rounded-lg px-3 py-2">
                Uses the HuggingFace Inference Router. Get your key at{" "}
                <span className="font-mono">huggingface.co/settings/tokens</span>
              </div>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">HuggingFace API Key</span>
                <input
                  type="password"
                  className="input"
                  value={settings.huggingface_api_key || ""}
                  onChange={(e) => set("huggingface_api_key", e.target.value)}
                  placeholder="hf_..."
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Model</span>
                <select
                  className="input"
                  value={settings.huggingface_model || "Qwen/Qwen3-Coder-30B-A3B-Instruct"}
                  onChange={(e) => set("huggingface_model", e.target.value)}
                >
                  <option value="Qwen/Qwen3-Coder-30B-A3B-Instruct">Qwen3-Coder-30B-A3B-Instruct (recommended)</option>
                  <option value="Qwen/Qwen2.5-Coder-32B-Instruct">Qwen2.5-Coder-32B-Instruct</option>
                  <option value="meta-llama/Llama-3.3-70B-Instruct">Llama-3.3-70B-Instruct</option>
                </select>
              </label>
            </div>
          )}

          {settings.provider === "ollama" && (
            <div className="space-y-3">
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Ollama Base URL</span>
                <input
                  className="input"
                  value={settings.ollama_base_url || "http://localhost:11434"}
                  onChange={(e) => set("ollama_base_url", e.target.value)}
                />
              </label>
              <label className="block">
                <span className="text-xs text-slate-500 mb-1 block">Model</span>
                <input
                  className="input"
                  value={settings.ollama_model || "qwen2.5-coder:7b"}
                  onChange={(e) => set("ollama_model", e.target.value)}
                  placeholder="qwen2.5-coder:7b, qwen2.5-coder:14b, codellama..."
                />
              </label>
            </div>
          )}
        </div>

        {/* Output directory */}
        <div className="card space-y-3">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-widest">
            Output Directory
          </h2>
          <label className="block">
            <span className="text-xs text-slate-500 mb-1 block">
              Generated projects will be saved here
            </span>
            <input
              className="input font-mono text-sm"
              value={settings.output_directory || ""}
              onChange={(e) => set("output_directory", e.target.value)}
              placeholder="C:/Users/you/autodev-projects"
            />
          </label>
        </div>

        {error && <p className="text-danger text-sm">{error}</p>}

        <button type="submit" className="btn-primary" disabled={saving}>
          {saving ? "Saving..." : saved ? "✓ Saved!" : "Save Settings"}
        </button>
      </form>
    </div>
  );
}
