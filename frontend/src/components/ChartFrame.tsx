import { useId, useState, type ReactNode } from 'react';
import { Legend, type LegendItem } from './Legend';

interface Props {
  title: string;
  /** One plain sentence on what to look for. */
  description: string;
  /** Legend shown whenever the chart has two or more series or colours. */
  legend?: LegendItem[];
  chart: ReactNode;
  table: ReactNode;
  /** Extra controls placed beside the Chart / Table switch. */
  controls?: ReactNode;
}

/** Every chart sits in this frame so a table is always one click behind it. */
export function ChartFrame({ title, description, legend, chart, table, controls }: Props) {
  const [mode, setMode] = useState<'chart' | 'table'>('chart');
  const id = useId();
  return (
    <section className="chart-frame" aria-labelledby={`${id}-h`}>
      <div className="chart-head">
        <div>
          <h3 id={`${id}-h`}>{title}</h3>
          <p className="muted">{description}</p>
        </div>
        <div className="chart-tools">
          {controls}
          <div className="seg" role="group" aria-label={`${title}: view`}>
            <button type="button" aria-pressed={mode === 'chart'} onClick={() => setMode('chart')}>Chart</button>
            <button type="button" aria-pressed={mode === 'table'} onClick={() => setMode('table')}>Table</button>
          </div>
        </div>
      </div>
      {legend && legend.length >= 2 && mode === 'chart' ? <Legend items={legend} /> : null}
      {mode === 'chart' ? chart : table}
    </section>
  );
}
