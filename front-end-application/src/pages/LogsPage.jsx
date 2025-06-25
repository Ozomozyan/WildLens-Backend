/* ─── src/pages/LogsPage.jsx ───────────────────────────────────── */
import { useEffect, useState } from "react";
import { useAuth }            from "../context/AuthContext.jsx";
import { fetchLogs,
         triggerETL,
         triggerTraining,
         triggerHpSearch,
         downloadBestConfig } from "../services/DataService.js";
import Navbar                 from "../components/Navbar.jsx";

export default function LogsPage() {
  const { user } = useAuth();
  const token    = user?.token ?? localStorage.getItem("token");

  /* ------------ logs ------------ */
  const [logText, setLogText] = useState("");
  const [error,   setError]   = useState(null);

  /* ------------ action feedback --*/
  const [actionMsg, setActionMsg] = useState("");

  const [trials, setTrials] = useState(20);
  const [study,  setStudy]  = useState("prod");
  const [yaml,   setYaml]   = useState("");     // best_config.yaml text

  /* ------------ training form ----*/
  const [batch,  setBatch]  = useState(32);
  const [epochs, setEpochs] = useState(10);

  /* ------------ load logs on mount */
  useEffect(() => {
    if (!token) return;
    fetchLogs({ lines: 400, token })
      .then(setLogText)
      .catch(() => setError("Cannot fetch logs"));
  }, [token]);

  /* ------------ handlers ----------*/
  const handleRunETL = async () => {
    try {
      setActionMsg("⏳ Triggering ETL…");
      const { message, error } = await triggerETL(token);
      setActionMsg(error ? `❌ ${error}` : `✅ ${message}`);
    } catch (e) {
      setActionMsg(`❌ ${e.message}`);
    }
  };

  const handleRunTraining = async (e) => {
    e.preventDefault();
    try {
      setActionMsg("⏳ Starting training job…");
      const { detail } = await triggerTraining({ batch, epochs, token });
      setActionMsg(`✅ ${detail}`);
    } catch (e) {
      /* 409 means “already running” */
      const msg = e?.response?.data?.detail || e.message;
      setActionMsg(`❌ ${msg}`);
    }
  };

  const handleRunHpSearch = async (e) => {
    e.preventDefault();
    try {
      setYaml(""); 
      setActionMsg("⏳ Launching hyper-param search…");
      await triggerHpSearch({ trials, study, token });
      setActionMsg("✅ Search started — polling for result…");

      // ⌛️ simple polling every 5 s until ready
      const poll = setInterval(async () => {
        try {
          const res = await downloadBestConfig({ study, token });
      
          if (res.status === 200) {                      // ← SUCCESS only on 200
            clearInterval(poll);
            setYaml(res.data);
            setActionMsg("✅ Search finished — best_config.yaml loaded 👇");
          }
          // else status 202 → keep waiting
        } catch (err) {
          if (![202, 404].includes(err.response?.status)) {
            clearInterval(poll);
            setActionMsg("❌ " + (err.message || "AI service error"));
          }
        }
      }, 5000);
    } catch (err) {
      setActionMsg("❌ " + (err.message || "AI service error"));
    }
  };

  /* ------------ render ------------*/
  if (error) {
    return <p className="p-6 text-red-500">{error}</p>;
  }

  return (
    <>
      <Navbar />

      <div className="p-6 space-y-6">
        <h1 className="text-2xl font-bold">Backend Utilities</h1>

        {/*  -----------------  ACTIONS  ----------------- */}
        <div className="space-x-4">
          <button
            onClick={handleRunETL}
            className="px-3 py-1 rounded bg-blue-600 hover:bg-blue-700 text-white"
          >
            🚀 Run ETL now
          </button>

          <form onSubmit={handleRunTraining} className="inline-flex items-center space-x-2">
            <label className="text-sm">
              Batch&nbsp;
              <input
                type="number" min="1"
                value={batch}
                onChange={e => setBatch(+e.target.value)}
                className="border w-16 px-1"
              />
            </label>

            <label className="text-sm">
              Epochs&nbsp;
              <input
                type="number" min="1"
                value={epochs}
                onChange={e => setEpochs(+e.target.value)}
                className="border w-16 px-1"
              />
            </label>

            <button className="px-3 py-1 rounded bg-green-600 hover:bg-green-700 text-white">
              🏋️ Train model
            </button>
          </form>

          {/*  --- Hyper-param Search form --------------------------------*/ }
          <form onSubmit={handleRunHpSearch} className="inline-flex items-center space-x-2">
            <label className="text-sm">
              Trials&nbsp;
              <input type="number" min="1"
                     value={trials}
                     onChange={e => setTrials(+e.target.value)}
                     className="border w-20 px-1" />
            </label>
  
            <label className="text-sm">
              Study&nbsp;
              <input type="text"
                     value={study}
                     onChange={e => setStudy(e.target.value)}
                     className="border w-24 px-1" />
            </label>
  
            <button className="px-3 py-1 rounded bg-purple-600 hover:bg-purple-700 text-white">
              🔎 HP-Search
            </button>
          </form>

          {actionMsg && (
            <span className="ml-4 text-sm">{actionMsg}</span>
          )}
          {yaml && (
            <details className="mt-2 bg-gray-100 rounded p-2">
              <summary className="cursor-pointer">best_config.yaml</summary>
              <pre className="whitespace-pre-wrap text-xs overflow-auto max-h-72">
                {yaml}
              </pre>
            </details>
          )}
        </div>

        {/*  -----------------  LOGS  ----------------- */}
        <h2 className="text-xl font-semibold">
          Backend Logs&nbsp;<span className="font-normal">(last 400 lines)</span>
        </h2>

        <pre className="bg-black text-green-300 p-4 overflow-auto rounded h-[60vh]">
          {logText || "Loading…"}
        </pre>
      </div>
    </>
  );
}
