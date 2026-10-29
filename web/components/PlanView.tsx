"use client";

import { Button, Col, Collapse, Row, Space, Typography } from "antd";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";

import type { PlanDocument } from "@/lib/api";
import { asOf, duration, miles, money } from "@/lib/format";

import StopTable from "./StopTable";

const { Text } = Typography;

// MapLibre needs the browser (WebGL), so it never renders on the server.
const RouteMap = dynamic(() => import("./RouteMap"), {
  ssr: false,
  loading: () => <div className="route-map" />,
});

function stopCount(n: number) {
  return n === 1 ? "1 stop" : `${n} stops`;
}

export default function PlanView({ doc }: { doc: PlanDocument }) {
  const [copied, setCopied] = useState(false);
  const { plan, baseline, inputs: i } = doc;

  async function copyLink() {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <Space direction="vertical" size={12} style={{ width: "100%" }}>
      <Text strong>
        {`${doc.from.label} → ${doc.to.label} · ${miles(doc.route.distance_mi)} · ${duration(doc.route.duration_min)}`}
      </Text>

      <div>
        <Typography.Title level={4} className="num" style={{ margin: 0 }}>
          {`Fuel ${money(plan.cost)}`}
        </Typography.Title>
        <Text type="secondary">
          {`${money(plan.spend)} at the pump, minus ${money(plan.leftover_value)} of fuel still in the tank at the end`}
        </Text>
      </div>

      <Text>
        {doc.savings >= 0.01
          ? `${money(doc.savings)} less than filling up at a quarter tank`
          : "Same as filling up at a quarter tank"}
      </Text>

      <Row gutter={[12, 12]}>
        <Col xs={24} lg={10}>
          <RouteMap
            route={doc.route.geometry.coordinates}
            stops={plan.stops}
            from={doc.from}
            to={doc.to}
          />
        </Col>
        <Col xs={24} lg={14}>
          <Space direction="vertical" size={12} style={{ width: "100%" }}>
            {plan.stops.length ? (
              <StopTable part={plan} />
            ) : (
              <Text>No stop needed: the tank covers the trip.</Text>
            )}
            <Collapse
              size="small"
              items={[
                {
                  key: "habit",
                  label: `Quarter-tank habit: ${stopCount(baseline.stops.length)}, ${money(baseline.cost)}`,
                  children: <StopTable part={baseline} />,
                },
              ]}
            />
          </Space>
        </Col>
      </Row>

      <Text type="secondary" style={{ fontSize: 12 }}>
        {`Prices: ${doc.prices.source}, as of ${asOf(doc.prices.as_of)} · Truck ${i.mpg} mpg, ${i.tank_gal} gal, ${i.start_pct}% at start, ${i.reserve_pct}% reserve, stations within ${i.max_detour_mi} mi`}
      </Text>

      <Space>
        <Button size="small" onClick={copyLink}>
          {copied ? "copied" : "Copy link"}
        </Button>
        <Link href={`/?plan=${doc.id}`}>Edit trip</Link>
      </Space>
    </Space>
  );
}
