import type { ReactNode } from 'react';

export interface Column<R> {
  header: string;
  /** Numeric columns are right-aligned with tabular figures. */
  numeric?: boolean;
  cell: (row: R) => ReactNode;
}

interface Props<R> {
  caption: string;
  columns: Column<R>[];
  rows: R[];
  rowKey: (row: R) => string;
}

/** Plain table behind a chart. Scrolls sideways on narrow screens and is reachable by keyboard. */
export function DataTable<R>({ caption, columns, rows, rowKey }: Props<R>) {
  return (
    <div className="table-scroll" tabIndex={0} role="region" aria-label={caption}>
      <table className="dt">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.header} scope="col" className={c.numeric ? 'num-col' : undefined}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)}>
              {columns.map((c) => (
                <td key={c.header} className={c.numeric ? 'num-col num' : undefined}>{c.cell(r)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
