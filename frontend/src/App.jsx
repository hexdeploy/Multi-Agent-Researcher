import React, { useState, useEffect } from 'react';
import { Search, Loader2, Sparkles, AlertCircle, Download, Cpu, ShieldCheck, MessageSquare, Clock, Trash2, CheckCircle2, UserCheck } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import './App.css';
import bgImage from './assets/bg-network.jpg';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

const RobotAvatar = ({ name, role, description, status }) => {
  return (
    <div className={`agent-card ${status}`}>
      <div className="agent-top">
        <div className="robot-head">
          <div className="robot-visor">
            <div className="robot-eye"></div>
            <div className="robot-eye"></div>
          </div>
        </div>
        <div className="agent-info">
          <div className="agent-name-row">
            <h3 className="agent-name">{name}</h3>
            {status === 'running' && <span className="pill-active">Active</span>}
            {status === 'paused' && <span className="pill-active">Awaiting Review</span>}
            {status === 'completed' && <span className="pill-ready">Ready</span>}
          </div>
          <span className="agent-role">{role}</span>
        </div>
      </div>
      <p className="agent-desc">"{description}"</p>
    </div>
  );
};

const formatDate = (timestamp) =>
  new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

export default function App() {
  const [topic, setTopic] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [history, setHistory] = useState([]);

  // Human-in-the-Loop state
  const [awaitingApproval, setAwaitingApproval] = useState(false);
  const [threadId, setThreadId] = useState('');
  const [editablePlan, setEditablePlan] = useState('');

  useEffect(() => {
    const savedHistory = JSON.parse(localStorage.getItem('researchHistory') || '[]');
    setHistory(savedHistory);
  }, []);

  const [agentLogs, setAgentLogs] = useState([
    { agent: 'System', message: 'Hello! Robot Swarm online. Enter a topic to begin.', time: 'Just now' }
  ]);

  const [agentStatuses, setAgentStatuses] = useState({
    researcher: 'idle',
    fact_checker: 'idle',
    analyst: 'idle',
    writer: 'idle',
  });

  const addLog = (agent, message) => {
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    setAgentLogs(prev => [{ agent, message, time }, ...prev]);
  };

  const processStream = async (response, currentTopic) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalReportContent = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.substring(6));
          if (data.error) throw new Error(data.error);

          if (data.status === 'awaiting_approval') {
            setThreadId(data.thread_id);
            setEditablePlan(data.plan);
            setAwaitingApproval(true);
            setLoading(false);
            setAgentStatuses({ researcher: 'paused', fact_checker: 'idle', analyst: 'idle', writer: 'idle' });
            addLog('Alpha (Planner)', 'Drafted research plan. Paused for human review and approval.');
            return;
          }

          if (data.status === 'completed') {
            setLoading(false);
            break;
          }

          if (data.node) {
            const node = data.node;
            const state = data.state;

            if (state.final_report) finalReportContent = state.final_report;

            if (node === 'planner') {
              addLog('Alpha (Planner)', 'Generated initial research angles.');
            } else if (node === 'researcher') {
              addLog('Alpha (Researcher)', 'Raw research collection complete!');
              setAgentStatuses({ researcher: 'completed', fact_checker: 'running', analyst: 'idle', writer: 'idle' });
              addLog('Beta (Fact-Checker)', 'Auditing data sources...');
            } else if (node === 'fact_checker') {
              const score = state.confidence_score;
              const retries = state.retry_count;
              if (score === 'LOW' && retries < 2) {
                addLog('Beta (Fact-Checker)', `Confidence LOW (Retry ${retries}/2). Digging deeper.`);
                setAgentStatuses({ researcher: 'running', fact_checker: 'running', analyst: 'idle', writer: 'idle' });
              } else {
                addLog('Beta (Fact-Checker)', 'Confidence HIGH. Passing notes to Gamma.');
                setAgentStatuses({ researcher: 'completed', fact_checker: 'completed', analyst: 'running', writer: 'idle' });
                addLog('Gamma (Analyst)', 'Analyzing patterns and trends...');
              }
            } else if (node === 'analyst') {
              addLog('Gamma (Analyst)', 'Synthesis complete! Handing off to Delta.');
              setAgentStatuses({ researcher: 'completed', fact_checker: 'completed', analyst: 'completed', writer: 'running' });
              addLog('Delta (Writer)', 'Compiling Markdown report...');
            } else if (node === 'writer') {
              addLog('Delta (Writer)', 'Report compilation finished!');
              setAgentStatuses({ researcher: 'completed', fact_checker: 'completed', analyst: 'completed', writer: 'completed' });

              const finalResult = {
                id: Date.now(),
                topic: state.topic || currentTopic,
                final_report: finalReportContent,
                confidence_score: state.confidence_score,
                retry_count: state.retry_count,
                timestamp: new Date().toISOString(),
              };

              setResult(finalResult);
              setHistory(prev => {
                const updated = [finalResult, ...prev].slice(0, 10);
                localStorage.setItem('researchHistory', JSON.stringify(updated));
                return updated;
              });
            }
          }
        }
      }
    }
  };

  const handleResearch = async (e) => {
    e.preventDefault();
    if (!topic.trim()) return;

    setLoading(true);
    setError('');
    setResult(null);
    setAwaitingApproval(false);

    setAgentLogs([{ agent: 'System', message: `Deploying swarm for: "${topic}"...`, time: new Date().toLocaleTimeString() }]);
    setAgentStatuses({ researcher: 'running', fact_checker: 'idle', analyst: 'idle', writer: 'idle' });
    addLog('Alpha (Planner)', 'Drafting structured research plan...');

    try {
      const response = await fetch(`${API_BASE_URL}/api/stream-research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
      });

      if (!response.ok) throw new Error('Failed to initiate research stream.');
      await processStream(response, topic);
    } catch (err) {
      setError(err.message);
      addLog('System', `Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleApprovePlan = async () => {
    if (!threadId) return;

    setAwaitingApproval(false);
    setLoading(true);
    setAgentStatuses({ researcher: 'running', fact_checker: 'idle', analyst: 'idle', writer: 'idle' });
    addLog('Human', 'Approved research plan. Resuming autonomous swarm...');
    addLog('Alpha (Researcher)', 'Scanning Wikipedia, DuckDuckGo, and arXiv...');

    try {
      const response = await fetch(`${API_BASE_URL}/api/resume-research`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: threadId,
          approved_plan: editablePlan,
        }),
      });

      if (!response.ok) throw new Error('Failed to resume research stream.');
      await processStream(response, topic);
    } catch (err) {
      setError(err.message);
      addLog('System', `Error: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!result) return;
    const blob = new Blob([result.final_report], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${result.topic.toLowerCase().replace(/\s+/g, '-')}-research-report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const loadHistoryItem = (item) => {
    setResult(item);
    setTopic(item.topic);
    setAwaitingApproval(false);
    setAgentLogs([{ agent: 'System', message: `Loaded report: "${item.topic}"`, time: formatDate(item.timestamp) }]);
    setAgentStatuses({ researcher: 'completed', fact_checker: 'completed', analyst: 'completed', writer: 'completed' });
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem('researchHistory');
    setResult(null);
  };

  return (
    <div className="app-wrapper" style={{ backgroundImage: `url(${bgImage})` }}>
      <div className="bg-overlay"></div>

      {/* Header */}
      <header className="top-header">
        <div className="brand-box">
          <div className="brand-icon">
            <Cpu size={22} color="#fff" />
          </div>
          <h1 className="brand-title">Multi-Agent Research Assistant</h1>
        </div>
        <div className="status-pill">
          <span className="status-dot"></span>
          <span>Robot Swarm Online</span>
        </div>
      </header>

      {/* Main Split Container */}
      <div className="dashboard-layout">
        {/* LEFT SIDEBAR: History */}
        <aside className="history-sidebar">
          <div className="sidebar-header">
            <div className="sidebar-title">
              <Clock size={18} color="#818cf8" />
              <span>Research History</span>
            </div>
            {history.length > 0 && (
              <button onClick={clearHistory} className="clear-btn" title="Clear History">
                <Trash2 size={16} />
              </button>
            )}
          </div>

          {history.length === 0 ? (
            <div className="empty-history">
              No reports generated yet. Deploy agents to start.
            </div>
          ) : (
            <ul className="history-list">
              {history.map(item => (
                <li key={item.id}>
                  <button
                    onClick={() => loadHistoryItem(item)}
                    className={`history-item-btn ${result?.id === item.id ? 'active' : ''}`}
                  >
                    <div className="history-item-top">
                      <span className="history-topic">{item.topic}</span>
                      <span className={item.confidence_score === 'HIGH' ? 'badge-high' : 'badge-low'}>
                        {item.confidence_score}
                      </span>
                    </div>
                    <div className="history-time">
                      <Clock size={12} />
                      <span>{formatDate(item.timestamp)}</span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* RIGHT MAIN WORKSPACE */}
        <main className="main-workspace">
          {/* Big Search Box */}
          <div className="search-card">
            <form onSubmit={handleResearch} className="search-form">
              <div className="search-input-wrap">
                <Search className="search-icon" size={22} />
                <input
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="Enter research topic (e.g., Quantum Computing in 2026, Agentic RAG)..."
                  className="search-input"
                />
              </div>
              <button
                type="submit"
                disabled={loading || !topic.trim()}
                className="deploy-btn"
              >
                {loading ? (
                  <>
                    <Loader2 size={20} className="animate-spin" />
                    <span>Swarm Active...</span>
                  </>
                ) : (
                  <>
                    <Sparkles size={20} />
                    <span>Deploy Agents</span>
                  </>
                )}
              </button>
            </form>
          </div>

          {/* Human-in-the-Loop Plan Approval Checkpoint */}
          {awaitingApproval && (
            <div className="hitl-card">
              <div className="hitl-header">
                <div className="hitl-title">
                  <UserCheck size={20} color="#818cf8" />
                  <span>Human-in-the-Loop: Review Research Plan</span>
                </div>
                <span className="hitl-badge">Checkpoint Paused</span>
              </div>
              <p className="hitl-subtitle">
                Alpha proposed the following research angles. Edit, add, or refine any points below before the swarm executes web and arXiv searches:
              </p>
              <textarea
                value={editablePlan}
                onChange={(e) => setEditablePlan(e.target.value)}
                className="hitl-textarea"
              />
              <div className="hitl-actions">
                <button onClick={handleApprovePlan} className="approve-btn">
                  <CheckCircle2 size={18} />
                  <span>Approve & Execute Swarm</span>
                </button>
              </div>
            </div>
          )}

          {/* 4 Agents Grid */}
          <div className="agents-grid">
            <RobotAvatar
              name="Alpha"
              role="Senior Researcher"
              description="Plans research angles and sweeps Wikipedia, Web, and arXiv."
              status={agentStatuses.researcher}
            />
            <RobotAvatar
              name="Beta"
              role="Fact-Checker"
              description="Audits data, verifies claims, and assesses reliability."
              status={agentStatuses.fact_checker}
            />
            <RobotAvatar
              name="Gamma"
              role="Strategic Analyst"
              description="Synthesizes patterns, trends, and knowledge gaps."
              status={agentStatuses.analyst}
            />
            <RobotAvatar
              name="Delta"
              role="Technical Writer"
              description="Compiles final Markdown report with citations."
              status={agentStatuses.writer}
            />
          </div>

          {/* Bottom Split: Live Logs & Final Report */}
          <div className="bottom-split">
            <div className="logs-panel">
              <div className="panel-header">
                <MessageSquare size={18} color="#818cf8" />
                <span>Live Agent Logs</span>
              </div>
              <div className="logs-box">
                {agentLogs.map((log, idx) => (
                  <div key={idx} className="log-entry">
                    <span className="log-time">[{log.time}]</span>
                    <span className={`log-agent ${log.agent === 'System' ? 'sys' : ''}`}>
                      {log.agent}:
                    </span>
                    <span className="log-msg">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>

            {result && (
              <div className="report-panel">
                <div className="report-header">
                  <div>
                    <div className="report-tag">
                      <ShieldCheck size={16} />
                      <span>Verified Intelligence Report</span>
                    </div>
                    <h2 className="report-title">{result.topic}</h2>
                  </div>

                  <div className="report-actions">
                    <div className="conf-box">
                      Confidence:{' '}
                      <strong style={{ color: result.confidence_score === 'HIGH' ? '#34d399' : '#fbbf24' }}>
                        {result.confidence_score}
                      </strong>
                    </div>
                    <button onClick={handleDownload} className="export-btn">
                      <Download size={16} />
                      <span>Export .md</span>
                    </button>
                  </div>
                </div>

                <div className="markdown-body">
                  <ReactMarkdown>{result.final_report}</ReactMarkdown>
                </div>
              </div>
            )}

            {error && (
              <div className="error-banner">
                <AlertCircle size={22} />
                <span>{error}</span>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}