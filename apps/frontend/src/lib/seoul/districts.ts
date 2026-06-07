// ⚠️ 자동 생성 파일 — 수기 편집 금지.
// 생성: python _build/gen_seoul_fe_data.py
// 출처: data/gold/seoul_district_scores.json (PHASE_PLAN 확정 SSOT) + config hot
// 생성시각: 2026-06-07T02:03:39.586905
// TODO: 실데이터 연동 시 GET /api/v1/commercial-districts?region=seoul 로 대체.

export type Phase = 1 | 2 | 3 | 4;
export type Criterion = "SNS" | "VAC" | "MAP" | "FOOT";

export interface SeoulDistrict {
  name: string;
  code: string;
  hot: string;            // 대표 상권
  rank: number;           // 점수순위(1~25, total 기준)
  total: number;          // 합산 점수(최대 32)
  sumB2C: number;         // B2C 합(최대 16)
  sumB2B: number;         // B2B 합(최대 16)
  b2c: Record<Criterion, number>;
  b2b: Record<Criterion, number>;
  phase: Phase;           // 진입 Phase (PHASE_PLAN)
  phaseSeq: number;       // Phase 내 진입 순번
  deployOrder: number;    // 전체 진입 순번(1~25)
}

export interface PhaseMeta { label: string; color: string; range: [number, number]; count: number; }

export const PHASE_COLORS: Record<Phase, string> = { 1: "#E8543B", 2: "#2E6FB7", 3: "#7FA8C9", 4: "#B8C2CC" };

export const PHASE_META: Record<Phase, PhaseMeta> = {
  1: { label: "Phase 1 · 진입 1~5", color: "#E8543B", range: [1, 5], count: 5 },
  2: { label: "Phase 2 · 진입 6~12", color: "#2E6FB7", range: [6, 12], count: 7 },
  3: { label: "Phase 3 · 진입 13~19", color: "#7FA8C9", range: [13, 19], count: 7 },
  4: { label: "Phase 4 · 진입 20~25", color: "#B8C2CC", range: [20, 25], count: 6 },
};

// 진입 순서(deployOrder) 오름차순.
export const SEOUL_DISTRICTS: SeoulDistrict[] = [
  {"name": "강남구", "code": "11230", "hot": "강남대로·가로수길·압구정로데오·신사", "rank": 1, "total": 31, "sumB2C": 15, "sumB2B": 16, "b2c": {"SNS": 4, "VAC": 3, "MAP": 4, "FOOT": 4}, "b2b": {"SNS": 4, "VAC": 4, "MAP": 4, "FOOT": 4}, "phase": 1, "phaseSeq": 1, "deployOrder": 1},
  {"name": "마포구", "code": "11140", "hot": "홍대·연남동·합정·망원", "rank": 2, "total": 25, "sumB2C": 12, "sumB2B": 13, "b2c": {"SNS": 3, "VAC": 2, "MAP": 4, "FOOT": 3}, "b2b": {"SNS": 2, "VAC": 4, "MAP": 4, "FOOT": 3}, "phase": 1, "phaseSeq": 2, "deployOrder": 2},
  {"name": "종로구", "code": "11010", "hot": "익선동·삼청동·광장시장·서촌", "rank": 3, "total": 22, "sumB2C": 11, "sumB2B": 11, "b2c": {"SNS": 2, "VAC": 2, "MAP": 3, "FOOT": 4}, "b2b": {"SNS": 1, "VAC": 4, "MAP": 2, "FOOT": 4}, "phase": 1, "phaseSeq": 3, "deployOrder": 3},
  {"name": "중구", "code": "11020", "hot": "명동·을지로·동대문", "rank": 4, "total": 20, "sumB2C": 10, "sumB2B": 10, "b2c": {"SNS": 2, "VAC": 2, "MAP": 2, "FOOT": 4}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 2, "FOOT": 4}, "phase": 1, "phaseSeq": 4, "deployOrder": 4},
  {"name": "성동구", "code": "11040", "hot": "성수동·서울숲·뚝섬", "rank": 5, "total": 20, "sumB2C": 10, "sumB2B": 10, "b2c": {"SNS": 2, "VAC": 1, "MAP": 4, "FOOT": 3}, "b2b": {"SNS": 1, "VAC": 2, "MAP": 4, "FOOT": 3}, "phase": 1, "phaseSeq": 5, "deployOrder": 5},
  {"name": "용산구", "code": "11030", "hot": "이태원·한남동·용리단길·경리단길", "rank": 6, "total": 20, "sumB2C": 9, "sumB2B": 11, "b2c": {"SNS": 2, "VAC": 2, "MAP": 2, "FOOT": 3}, "b2b": {"SNS": 2, "VAC": 4, "MAP": 2, "FOOT": 3}, "phase": 2, "phaseSeq": 1, "deployOrder": 6},
  {"name": "송파구", "code": "11240", "hot": "잠실·송리단길·방이", "rank": 7, "total": 19, "sumB2C": 9, "sumB2B": 10, "b2c": {"SNS": 4, "VAC": 1, "MAP": 1, "FOOT": 3}, "b2b": {"SNS": 3, "VAC": 3, "MAP": 1, "FOOT": 3}, "phase": 2, "phaseSeq": 2, "deployOrder": 7},
  {"name": "광진구", "code": "11050", "hot": "건대입구·구의·성수연계", "rank": 8, "total": 19, "sumB2C": 9, "sumB2B": 10, "b2c": {"SNS": 3, "VAC": 1, "MAP": 3, "FOOT": 2}, "b2b": {"SNS": 2, "VAC": 3, "MAP": 3, "FOOT": 2}, "phase": 2, "phaseSeq": 3, "deployOrder": 8},
  {"name": "영등포구", "code": "11190", "hot": "여의도·문래동·영등포역", "rank": 9, "total": 18, "sumB2C": 9, "sumB2B": 9, "b2c": {"SNS": 2, "VAC": 1, "MAP": 2, "FOOT": 4}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 2, "FOOT": 3}, "phase": 2, "phaseSeq": 4, "deployOrder": 9},
  {"name": "서초구", "code": "11220", "hot": "고속터미널·서초·반포", "rank": 11, "total": 15, "sumB2C": 7, "sumB2B": 8, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 3}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 3}, "phase": 2, "phaseSeq": 5, "deployOrder": 10},
  {"name": "서대문구", "code": "11130", "hot": "신촌·이대·연희동", "rank": 14, "total": 15, "sumB2C": 7, "sumB2B": 8, "b2c": {"SNS": 2, "VAC": 2, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 4, "MAP": 1, "FOOT": 2}, "phase": 2, "phaseSeq": 6, "deployOrder": 11},
  {"name": "동대문구", "code": "11060", "hot": "청량리·DDP연계·회기", "rank": 10, "total": 17, "sumB2C": 9, "sumB2B": 8, "b2c": {"SNS": 2, "VAC": 2, "MAP": 2, "FOOT": 3}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 2, "FOOT": 2}, "phase": 2, "phaseSeq": 7, "deployOrder": 12},
  {"name": "관악구", "code": "11210", "hot": "샤로수길·서울대입구·신림", "rank": 17, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 1, "deployOrder": 13},
  {"name": "동작구", "code": "11200", "hot": "노량진·사당·흑석", "rank": 15, "total": 14, "sumB2C": 7, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 2, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 2, "deployOrder": 14},
  {"name": "강서구", "code": "11160", "hot": "마곡·발산·까치산", "rank": 16, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 3, "deployOrder": 15},
  {"name": "구로구", "code": "11170", "hot": "구로디지털·신도림·가산연계", "rank": 13, "total": 15, "sumB2C": 7, "sumB2B": 8, "b2c": {"SNS": 3, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 2, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 4, "deployOrder": 16},
  {"name": "금천구", "code": "11180", "hot": "가산디지털·독산", "rank": 20, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 5, "deployOrder": 17},
  {"name": "강동구", "code": "11250", "hot": "천호·강동역·고덕", "rank": 19, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 6, "deployOrder": 18},
  {"name": "노원구", "code": "11110", "hot": "노원역·공릉·중계", "rank": 18, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 3, "phaseSeq": 7, "deployOrder": 19},
  {"name": "성북구", "code": "11080", "hot": "성신여대·안암·길음", "rank": 12, "total": 15, "sumB2C": 7, "sumB2B": 8, "b2c": {"SNS": 2, "VAC": 1, "MAP": 2, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 2, "FOOT": 2}, "phase": 4, "phaseSeq": 1, "deployOrder": 20},
  {"name": "양천구", "code": "11150", "hot": "목동·오목교·신정", "rank": 21, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 4, "phaseSeq": 2, "deployOrder": 21},
  {"name": "은평구", "code": "11120", "hot": "연신내·불광·응암", "rank": 23, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 4, "phaseSeq": 3, "deployOrder": 22},
  {"name": "강북구", "code": "11090", "hot": "수유·미아·번동", "rank": 22, "total": 13, "sumB2C": 6, "sumB2B": 7, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 2}, "phase": 4, "phaseSeq": 4, "deployOrder": 23},
  {"name": "중랑구", "code": "11070", "hot": "상봉·면목·중화", "rank": 24, "total": 12, "sumB2C": 6, "sumB2B": 6, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 2}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 1}, "phase": 4, "phaseSeq": 5, "deployOrder": 24},
  {"name": "도봉구", "code": "11100", "hot": "창동·쌍문·방학", "rank": 25, "total": 11, "sumB2C": 5, "sumB2B": 6, "b2c": {"SNS": 2, "VAC": 1, "MAP": 1, "FOOT": 1}, "b2b": {"SNS": 1, "VAC": 3, "MAP": 1, "FOOT": 1}, "phase": 4, "phaseSeq": 6, "deployOrder": 25},
];

export const SEOUL_GENERATED_AT = "2026-06-07T02:03:39.586905";
