/* ─── src/pages/LogsPage.jsx ───────────────────────────────────── */
import { useEffect, useState } from "react";
import { useAuth }            from "../context/AuthContext.jsx";
import { fetchLogs,
         triggerETL,
         triggerTraining }     from "../services/DataService.js";
import Navbar                 from "../components/Navbar.jsx";

export default function LogsPage() {
  const { user } = useAuth();
  const token    = user?.token ?? localStorage.getItem("token");

  /* ------------ logs ------------ */
  const [logText, setLogText] = useState("");
  const [error,   setError]   = useState(null);

  /* ------------ action feedback --*/
  const [actionMsg, setActionMsg] = useState("");

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

          {actionMsg && (
            <span className="ml-4 text-sm">{actionMsg}</span>
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
