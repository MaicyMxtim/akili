import http from "k6/http";
import { check } from "k6";

// BASE_URL required; STAGE picks the profile:
//   steady  - 5 VUs for 2m (background load for chaos experiments)
//   ramp    - 2 -> 30 VUs over 6m (find saturation)
const profiles = {
  steady: [{ duration: "2m", target: 5 }],
  ramp: [
    { duration: "1m", target: 2 },
    { duration: "2m", target: 10 },
    { duration: "2m", target: 20 },
    { duration: "1m", target: 30 },
  ],
};

export const options = {
  stages: profiles[__ENV.STAGE || "steady"],
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

const bodies = [
  { postcode: "SW1A 1AA", property_type: "T", town: "LONDON", district: "WESTMINSTER", county: "GREATER LONDON" },
  { postcode: "M14 5TQ", property_type: "S", town: "MANCHESTER", district: "MANCHESTER", county: "GREATER MANCHESTER" },
  { postcode: "BS3 4NQ", property_type: "T", town: "BRISTOL", district: "BRISTOL", county: "BRISTOL" },
  { postcode: "LS6 2AS", property_type: "D", town: "LEEDS", district: "LEEDS", county: "WEST YORKSHIRE" },
];

export default function () {
  const body = bodies[Math.floor(Math.random() * bodies.length)];
  const res = http.post(`${__ENV.BASE_URL}/predict`, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "status 200": (r) => r.status === 200 });
}
