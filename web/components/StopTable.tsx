"use client";

import { Grid, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";

import type { PlanPart, Stop } from "@/lib/api";
import { gallons, milesExact, money, price } from "@/lib/format";

const num = (text: string) => <span className="num">{text}</span>;

export default function StopTable({ part }: { part: PlanPart }) {
  const wide = Grid.useBreakpoint().md;

  const columns: ColumnsType<Stop> = [
    { title: "#", key: "n", width: 32, render: (_, __, i) => i + 1 },
    {
      title: "Mile",
      dataIndex: "mile",
      responsive: ["md"],
      render: (m: number) => num(milesExact(m)),
    },
    {
      title: "Station",
      key: "station",
      render: (_, s) => (
        <>
          <div>{s.name}</div>
          {/* antd's break-word lets the column shrink until town names split mid-word */}
          <Typography.Text type="secondary" style={{ fontSize: 12, wordBreak: "normal" }}>
            {/* on a phone the mile column is hidden, so it rides along here, on its own
                line: inline, its no-wrap width pushed the Cost column off the screen */}
            {!wide && (
              <span className="num" style={{ display: "block" }}>
                mile {s.mile.toFixed(1)}
              </span>
            )}
            {s.city}, {s.state} · {s.address}
          </Typography.Text>
        </>
      ),
    },
    { title: "Price", dataIndex: "price", align: "right", render: (p: number) => num(price(p)) },
    { title: "Buy", dataIndex: "gallons", align: "right", render: (g: number) => num(gallons(g)) },
    { title: "Cost", dataIndex: "cost", align: "right", render: (c: number) => num(money(c)) },
    {
      title: "Detour",
      key: "detour",
      responsive: ["md"],
      render: (_, s) => (
        <>
          {num(milesExact(s.detour_mi))}
          <div>
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {gallons(s.detour_gal)} there and back
            </Typography.Text>
          </div>
        </>
      ),
    },
  ];

  return (
    <Table
      size="small"
      rowKey="opis_id"
      columns={columns}
      dataSource={part.stops}
      pagination={false}
    />
  );
}
