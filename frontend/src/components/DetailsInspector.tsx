import React, { useState } from 'react';
import { Terminal, Database, Sliders, ChevronDown, ChevronRight, Eye } from 'lucide-react';

interface DetailsInspectorProps {
  routing: any;
  apiResponse: any;
  team: string;
}

export const DetailsInspector: React.FC<DetailsInspectorProps> = ({
  routing,
  apiResponse,
  team,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'flow' | 'sql' | 'rag' | 'json'>('flow');

  if (!routing && !apiResponse) return null;

  const data = apiResponse?.data || apiResponse || {};
  const hasSql = !!data.sql;
  const hasRag = !!data.filters;

  const teamLabel = team === 'sales' ? 'Sales Team' : 'Purchase Team';
  const teamBadgeClass = team === 'sales' ? 'badge-sales' : 'badge-purchase';
  const documentType = (routing?.documentType || 'Document').replace('_', ' ').toUpperCase();
  const action = (routing?.action || 'Fetch').toUpperCase();
  const agentName = routing?.subagent || data?.agent || 'fetch_agent';

  return (
    <div style={styles.container}>
      <button style={styles.toggleHeader} onClick={() => setIsOpen(!isOpen)}>
        <div style={styles.headerTitle}>
          <Terminal size={16} color="#06b6d4" />
          <span>Technical Execution Details</span>
        </div>
        {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
      </button>

      {isOpen && (
        <div style={styles.contentBody}>
          {/* Console tabs */}
          <div style={styles.tabHeader}>
            <button
              style={{ ...styles.tabButton, ...(activeTab === 'flow' ? styles.tabButtonActive : {}) }}
              onClick={() => setActiveTab('flow')}
            >
              <Eye size={14} /> Execution Flow
            </button>
            {hasSql && (
              <button
                style={{ ...styles.tabButton, ...(activeTab === 'sql' ? styles.tabButtonActive : {}) }}
                onClick={() => setActiveTab('sql')}
              >
                <Database size={14} /> HANA SQL
              </button>
            )}
            {hasRag && (
              <button
                style={{ ...styles.tabButton, ...(activeTab === 'rag' ? styles.tabButtonActive : {}) }}
                onClick={() => setActiveTab('rag')}
              >
                <Sliders size={14} /> RAG Filters
              </button>
            )}
            <button
              style={{ ...styles.tabButton, ...(activeTab === 'json' ? styles.tabButtonActive : {}) }}
              onClick={() => setActiveTab('json')}
            >
              JSON Response
            </button>
          </div>

          {/* Console content */}
          <div style={styles.tabContent}>
            {activeTab === 'flow' && (
              <div style={styles.flowSection}>
                <div style={styles.flowBreadcrumb}>
                  <span style={styles.flowNode}>Big Supervisor</span>
                  <span style={styles.flowArrow}>→</span>
                  <span className={`badge ${teamBadgeClass}`}>{teamLabel}</span>
                  <span style={styles.flowArrow}>→</span>
                  <span style={styles.flowNodeActive}>{action} {documentType} Agent</span>
                </div>
                <div style={styles.flowDetailList}>
                  <div style={styles.flowDetailRow}>
                    <span style={styles.flowDetailKey}>Target Sub-Agent:</span>
                    <code style={styles.codeText}>{agentName}</code>
                  </div>
                  {data.strategy && (
                    <div style={styles.flowDetailRow}>
                      <span style={styles.flowDetailKey}>Fetch Strategy:</span>
                      <span style={styles.strategyLabel}>{data.strategy}</span>
                    </div>
                  )}
                  {data.workflow && (
                    <div style={styles.flowDetailRow}>
                      <span style={styles.flowDetailKey}>Sub-Agent Steps:</span>
                      <div style={styles.workflowSteps}>
                        {data.workflow.map((step: string, i: number) => (
                          <div key={i} style={styles.workflowStep}>
                            <span style={styles.stepNum}>{i + 1}</span> {step}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'sql' && hasSql && (
              <div style={styles.codeContainer}>
                <pre style={styles.preCode}>
                  <code style={styles.sqlCode}>{data.sql}</code>
                </pre>
              </div>
            )}

            {activeTab === 'rag' && hasRag && (
              <div style={styles.ragDetails}>
                {data.filters.retrievedSchema && (
                  <div style={styles.ragSection}>
                    <div style={styles.ragSubHeader}>Matched Schema Metadata</div>
                    <div style={styles.ragPills}>
                      {data.filters.retrievedSchema.map((sch: string, i: number) => (
                        <span key={i} style={styles.ragPill}>{sch}</span>
                      ))}
                    </div>
                  </div>
                )}
                {data.filters.retrievedExamples && (
                  <div style={styles.ragSection}>
                    <div style={styles.ragSubHeader}>Retrieved Query Intents</div>
                    <div style={styles.ragPills}>
                      {data.filters.retrievedExamples.map((ex: string, i: number) => (
                        <span key={i} style={styles.ragPillAccent}>{ex}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {activeTab === 'json' && (
              <div style={styles.codeContainer}>
                <pre style={styles.preCode}>
                  <code style={styles.jsonCode}>
                    {JSON.stringify(apiResponse, null, 2)}
                  </code>
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  container: {
    backgroundColor: '#0f172a',
    border: '1px solid #1e293b',
    borderRadius: '8px',
    marginTop: '1rem',
    overflow: 'hidden',
    fontSize: '0.85rem',
  },
  toggleHeader: {
    width: '100%',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0.65rem 1rem',
    background: '#1e293b55',
    color: '#94a3b8',
    textAlign: 'left',
    border: 'none',
  },
  headerTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontWeight: 500,
    color: '#cbd5e1',
  },
  contentBody: {
    borderTop: '1px solid #1e293b',
    background: '#090d16',
  },
  tabHeader: {
    display: 'flex',
    borderBottom: '1px solid #1e293b',
    background: '#0d1322',
  },
  tabButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    padding: '0.5rem 1rem',
    color: '#64748b',
    fontSize: '0.8rem',
    fontWeight: 500,
    borderRight: '1px solid #1e293b',
    borderRadius: 0,
  },
  tabButtonActive: {
    color: '#06b6d4',
    background: '#090d16',
    borderBottom: '2px solid #06b6d4',
  },
  tabContent: {
    padding: '1rem',
    maxHeight: '350px',
    overflowY: 'auto',
  },
  flowSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  flowBreadcrumb: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    flexWrap: 'wrap',
    background: '#111827',
    padding: '8px 12px',
    borderRadius: '6px',
    border: '1px solid #1f2937',
  },
  flowNode: {
    color: '#94a3b8',
    fontWeight: 500,
  },
  flowArrow: {
    color: '#475569',
  },
  flowNodeActive: {
    color: '#38bdf8',
    fontWeight: 600,
  },
  flowDetailList: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  },
  flowDetailRow: {
    display: 'flex',
    alignItems: 'baseline',
    gap: '8px',
  },
  flowDetailKey: {
    color: '#64748b',
    width: '120px',
    flexShrink: 0,
  },
  codeText: {
    color: '#a78bfa',
    background: '#1e1b4b',
    padding: '2px 6px',
    borderRadius: '4px',
    fontFamily: 'monospace',
  },
  strategyLabel: {
    color: '#34d399',
    fontWeight: 600,
    textTransform: 'uppercase',
    fontSize: '0.75rem',
  },
  workflowSteps: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  workflowStep: {
    color: '#cbd5e1',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  stepNum: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    width: '18px',
    height: '18px',
    borderRadius: '50%',
    background: '#1e293b',
    color: '#94a3b8',
    fontSize: '10px',
    fontWeight: 600,
  },
  codeContainer: {
    margin: 0,
  },
  preCode: {
    margin: 0,
    overflowX: 'auto',
  },
  sqlCode: {
    color: '#38bdf8',
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
  },
  jsonCode: {
    color: '#cbd5e1',
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
  },
  ragDetails: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  ragSection: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  ragSubHeader: {
    color: '#64748b',
    fontWeight: 500,
    fontSize: '0.8rem',
  },
  ragPills: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '6px',
  },
  ragPill: {
    background: '#1e293b',
    color: '#cbd5e1',
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '0.75rem',
  },
  ragPillAccent: {
    background: '#1e1b4b',
    color: '#c084fc',
    padding: '3px 8px',
    borderRadius: '4px',
    fontSize: '0.75rem',
    border: '1px solid #581c8755',
  },
};
