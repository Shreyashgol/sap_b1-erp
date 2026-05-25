import React, { useState } from 'react';
import { BarChart2, TrendingUp, Info } from 'lucide-react';

interface DataChartProps {
  prompt: string;
  apiResponse: any;
}

export const DataChart: React.FC<DataChartProps> = ({ prompt, apiResponse }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const wantsChart = (text: string): boolean => {
    const lowered = text.toLowerCase();
    const chartTerms = [
      'chart', 'graph', 'plot', 'visualize', 'visualise',
      'bar chart', 'line chart', 'trend', 'dashboard'
    ];
    return chartTerms.some(term => lowered.includes(term));
  };

  const extractRows = (res: any): any[] => {
    if (!res || typeof res !== 'object') return [];
    const data = res.data || res || {};
    const rows = data.results || data.rows || data.value || [];
    return Array.isArray(rows) ? rows : [];
  };

  const flattenRow = (row: any): any => {
    const flattened: any = {};
    for (const key in row) {
      if (row[key] && typeof row[key] === 'object' && !Array.isArray(row[key])) {
        for (const childKey in row[key]) {
          flattened[`${key}_${childKey}`] = row[key][childKey];
        }
      } else if (!Array.isArray(row[key])) {
        flattened[key] = row[key];
      }
    }
    return flattened;
  };

  const rows = extractRows(apiResponse);
  if (!wantsChart(prompt) || rows.length === 0) return null;

  const flattenedRows = rows.map(r => flattenRow(r));
  const keys = Object.keys(flattenedRows[0] || {});

  // Identify numeric and text columns
  const numericColumns: string[] = [];
  const textColumns: string[] = [];

  flattenedRows.forEach(row => {
    keys.forEach(key => {
      const val = row[key];
      const num = Number(val);
      if (val !== null && val !== undefined && !isNaN(num) && typeof val !== 'boolean') {
        if (!numericColumns.includes(key)) numericColumns.push(key);
      } else {
        if (!textColumns.includes(key) && val !== null) textColumns.push(key);
      }
    });
  });

  // Filter keys that are purely numeric across all rows
  const finalNumericColumns = numericColumns.filter(col => 
    flattenedRows.every(row => {
      const v = row[col];
      return v === null || v === undefined || !isNaN(Number(v));
    })
  );

  if (finalNumericColumns.length === 0) {
    return (
      <div style={styles.infoBox}>
        <Info size={16} color="#3b82f6" />
        <span style={{ fontSize: '0.85rem' }}>
          I found tabular records for this query, but there are no numeric columns to plot.
        </span>
      </div>
    );
  }

  // Choose dimensions
  const dateLike = keys.find(k => k.toLowerCase().includes('date') || k.toLowerCase().includes('month') || k.toLowerCase().includes('year'));
  const xKey = dateLike || textColumns[0] || keys[0];
  const yKey = finalNumericColumns[0];

  // Prepare data points
  const chartData = flattenedRows
    .map(row => ({
      x: String(row[xKey] || ''),
      y: Number(row[yKey] || 0)
    }))
    .filter(d => d.x && !isNaN(d.y));

  if (chartData.length === 0) return null;

  const chartType = (prompt.toLowerCase().includes('line') || 
                     prompt.toLowerCase().includes('trend') || 
                     prompt.toLowerCase().includes('month') || 
                     prompt.toLowerCase().includes('date')) 
                     ? 'line' 
                     : prompt.toLowerCase().includes('area') 
                     ? 'area' 
                     : 'bar';

  // SVG Chart Calculation Configs
  const width = 600;
  const height = 280;
  const paddingLeft = 65;
  const paddingRight = 20;
  const paddingTop = 30;
  const paddingBottom = 45;

  const graphWidth = width - paddingLeft - paddingRight;
  const graphHeight = height - paddingTop - paddingBottom;

  const yValues = chartData.map(d => d.y);
  const maxY = Math.max(...yValues, 0) * 1.15 || 10;
  const minY = 0; // standard bar baseline

  const getX = (index: number) => paddingLeft + (index / Math.max(chartData.length - 1, 1)) * graphWidth;
  const getY = (val: number) => paddingTop + graphHeight - ((val - minY) / (maxY - minY)) * graphHeight;

  // Grid Lines
  const gridCount = 4;
  const gridLines = Array.from({ length: gridCount + 1 }).map((_, i) => {
    const val = minY + (i / gridCount) * (maxY - minY);
    const yPos = getY(val);
    return { val, yPos };
  });

  return (
    <div style={styles.card}>
      <div style={styles.cardHeader}>
        <div style={styles.titleGroup}>
          {chartType === 'bar' ? (
            <BarChart2 size={16} color="#06b6d4" />
          ) : (
            <TrendingUp size={16} color="#06b6d4" />
          )}
          <h4 style={styles.title}>
            Visualizing: {yKey.replace(/_/g, ' ')} by {xKey.replace(/_/g, ' ')}
          </h4>
        </div>
        <span style={styles.chartTypeBadge}>{chartType.toUpperCase()} CHART</span>
      </div>

      <div style={styles.chartWrapper}>
        <svg viewBox={`0 0 ${width} ${height}`} style={styles.svg}>
          {/* Y Axis Grid Lines */}
          {gridLines.map((line, idx) => (
            <g key={idx}>
              <line
                x1={paddingLeft}
                y1={line.yPos}
                x2={width - paddingRight}
                y2={line.yPos}
                stroke="#1e293b"
                strokeWidth={1}
                strokeDasharray="4 4"
              />
              <text
                x={paddingLeft - 8}
                y={line.yPos + 4}
                textAnchor="end"
                fill="#64748b"
                fontSize="10px"
              >
                {line.val >= 1e6 
                  ? `${(line.val / 1e6).toFixed(1)}M` 
                  : line.val >= 1e3 
                  ? `${(line.val / 1e3).toFixed(1)}k` 
                  : line.val.toFixed(0)}
              </text>
            </g>
          ))}

          {/* Bar Chart Path */}
          {chartType === 'bar' &&
            chartData.map((d, idx) => {
              const barWidth = Math.max((graphWidth / chartData.length) * 0.7, 4);
              const xPos = paddingLeft + (idx / chartData.length) * graphWidth + (graphWidth / chartData.length - barWidth) / 2;
              const yPos = getY(d.y);
              const barHeight = Math.max(graphHeight - (yPos - paddingTop), 1);
              const isHovered = hoveredIndex === idx;

              return (
                <rect
                  key={idx}
                  x={xPos}
                  y={yPos}
                  width={barWidth}
                  height={barHeight}
                  fill={isHovered ? '#22d3ee' : 'url(#barGradient)'}
                  rx={Math.min(barWidth / 4, 4)}
                  style={{ transition: 'all 0.15s ease', cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />
              );
            })}

          {/* Area Chart Path */}
          {chartType === 'area' && chartData.length > 1 && (
            <>
              <polygon
                points={`
                  ${getX(0)},${paddingTop + graphHeight}
                  ${chartData.map((d, idx) => `${getX(idx)},${getY(d.y)}`).join(' ')}
                  ${getX(chartData.length - 1)},${paddingTop + graphHeight}
                `}
                fill="url(#areaGradient)"
              />
              <path
                d={chartData.map((d, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx)} ${getY(d.y)}`).join(' ')}
                fill="none"
                stroke="#06b6d4"
                strokeWidth={2.5}
              />
            </>
          )}

          {/* Line Chart Path */}
          {chartType === 'line' && chartData.length > 1 && (
            <path
              d={chartData.map((d, idx) => `${idx === 0 ? 'M' : 'L'} ${getX(idx)} ${getY(d.y)}`).join(' ')}
              fill="none"
              stroke="#06b6d4"
              strokeWidth={3}
            />
          )}

          {/* Interaction Dots for Line & Area Charts */}
          {(chartType === 'line' || chartType === 'area') &&
            chartData.map((d, idx) => {
              const cx = getX(idx);
              const cy = getY(d.y);
              const isHovered = hoveredIndex === idx;

              return (
                <circle
                  key={idx}
                  cx={cx}
                  cy={cy}
                  r={isHovered ? 6 : 4}
                  fill={isHovered ? '#22d3ee' : '#09132c'}
                  stroke={isHovered ? '#ffffff' : '#06b6d4'}
                  strokeWidth={2.5}
                  style={{ transition: 'all 0.15s ease', cursor: 'pointer' }}
                  onMouseEnter={() => setHoveredIndex(idx)}
                  onMouseLeave={() => setHoveredIndex(null)}
                />
              );
            })}

          {/* X Axis Labels */}
          {chartData.map((d, idx) => {
            const cx = chartType === 'bar'
              ? paddingLeft + (idx / chartData.length) * graphWidth + (graphWidth / chartData.length) / 2
              : getX(idx);

            // Skip labels if they crowd too much
            const interval = Math.max(Math.ceil(chartData.length / 6), 1);
            if (idx % interval !== 0) return null;

            return (
              <text
                key={idx}
                x={cx}
                y={height - paddingBottom + 18}
                textAnchor="middle"
                fill="#64748b"
                fontSize="9px"
                transform={`rotate(-15, ${cx}, ${height - paddingBottom + 18})`}
              >
                {d.x.length > 12 ? `${d.x.substring(0, 10)}...` : d.x}
              </text>
            );
          })}

          {/* Definitions / Gradients */}
          <defs>
            <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" />
              <stop offset="100%" stopColor="#1e40af" />
            </linearGradient>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#06b6d4" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#1e40af" stopOpacity="0.0" />
            </linearGradient>
          </defs>
        </svg>

        {/* Hover Tooltip */}
        {hoveredIndex !== null && chartData[hoveredIndex] && (
          <div style={styles.tooltip}>
            <div style={styles.tooltipLabel}>{chartData[hoveredIndex].x}</div>
            <div style={styles.tooltipValue}>
              <span style={styles.tooltipValKey}>{yKey.replace(/_/g, ' ')}:</span>
              <span style={styles.tooltipValNum}>
                {chartData[hoveredIndex].y.toLocaleString(undefined, {
                  maximumFractionDigits: 2,
                })}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const styles: { [key: string]: React.CSSProperties } = {
  card: {
    backgroundColor: '#0f1c3f',
    border: '1px solid #1e293b',
    borderRadius: '12px',
    padding: '1.25rem',
    marginTop: '1.25rem',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.25)',
  },
  cardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: '1rem',
  },
  titleGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  title: {
    margin: 0,
    fontSize: '0.9rem',
    fontWeight: 600,
    color: '#f8fafc',
  },
  chartTypeBadge: {
    fontSize: '0.7rem',
    fontWeight: 700,
    color: '#06b6d4',
    letterSpacing: '1px',
    background: '#06b6d41a',
    padding: '2px 8px',
    borderRadius: '4px',
  },
  chartWrapper: {
    position: 'relative',
    width: '100%',
  },
  svg: {
    width: '100%',
    height: 'auto',
    display: 'block',
  },
  tooltip: {
    position: 'absolute',
    top: '10px',
    right: '10px',
    background: '#020617ee',
    border: '1px solid #1e293b',
    padding: '8px 12px',
    borderRadius: '6px',
    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
    zIndex: 10,
    pointerEvents: 'none',
    animation: 'fadeInUp 0.15s ease',
  },
  tooltipLabel: {
    fontSize: '0.75rem',
    fontWeight: 600,
    color: '#94a3b8',
    marginBottom: '2px',
  },
  tooltipValue: {
    fontSize: '0.8rem',
    display: 'flex',
    gap: '6px',
  },
  tooltipValKey: {
    color: '#cbd5e1',
  },
  tooltipValNum: {
    color: '#06b6d4',
    fontWeight: 700,
  },
  infoBox: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    background: '#1d4ed81a',
    border: '1px solid #3b82f633',
    padding: '10px 14px',
    borderRadius: '8px',
    marginTop: '1rem',
    color: '#cbd5e1',
  },
};
