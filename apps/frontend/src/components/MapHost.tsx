/**
 * MapHost — 앱 전체가 공유하는 **단 하나의** 네이버 지도.
 *
 * ## 왜 올렸나 (2026-09-05, 설계서 §10-1)
 *
 * 그전까지 지도는 `MapShell`(Page 탭) 안에서 태어나고 죽었다. 탭을 옮기면 컴포넌트가
 * 언마운트되면서 지도도 같이 사라지고, 돌아오면 새로 만들어졌다. SDK 재초기화 비용도
 * 비용이지만 더 큰 손실은 **사용자가 맞춰 둔 카메라(중심·줌)** 다 — 거점을 찾아 확대해
 * 놓고 잠깐 다른 탭을 보고 오면 서울 전역으로 되돌아가 있었다.
 *
 * 이제 지도는 여기서 한 번 태어나 앱이 닫힐 때까지 산다. 탭은 그 위에 뜨는
 * **오버레이 세트만 갈아끼운다**(`children`).
 *
 * ## 지도 뷰가 아닐 때
 *
 * 언마운트하지 않고 `visibility: hidden` 으로 숨긴다. `display: none` 은 컨테이너
 * 크기를 0 으로 만들어, 다시 보일 때 지도가 접힌 채로 남는다(SDK 에 resize 를 따로
 * 알려야 한다). `visibility` 는 레이아웃을 그대로 두므로 그 문제가 없다.
 *
 * ## 캔버스 사이징
 *
 * `inset:0` 만으로 크기를 잡지 말 것 — SDK 가 초기화하면서 컨테이너의 position 을
 * relative 로 덮어써서 inset 이 오프셋으로 해석되고 높이가 0 으로 접힌다
 * (2026-08-01 실측). `width/height:100%` 를 같이 준다.
 */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { loadNaverMaps, describeNaverMapError } from "@/lib/naverMap";
import "./MapHost.css";

/** 가로수길 코어 — 거점 목록이 오기 전 초기 중심(poc-building-vacancy.md §0.5). */
const GAROSU = { lat: 37.5205, lng: 127.023 };

export interface MapHostValue {
  /** 준비되기 전에는 null. 소비하는 쪽은 `ready` 로 가른다. */
  map: any | null;
  ready: boolean;
  /** 지도 자체를 못 띄운 이유(도메인 미등록 등). 원인과 조치가 한 줄에 같이 온다. */
  error: string | null;
}

const MapHostCtx = createContext<MapHostValue>({ map: null, ready: false, error: null });

/** 오버레이 컴포넌트가 공유 지도를 받는 창구. */
export function useMapHost(): MapHostValue {
  return useContext(MapHostCtx);
}

export default function MapHost({ active, children }: { active: boolean; children: ReactNode }) {
  const elRef = useRef<HTMLDivElement>(null);
  // ⚠ 지도 인스턴스를 **두 곳**에 둔다. 하나로 줄이지 말 것.
  //   mapRef  — 동기 중복생성 가드. StrictMode 는 이펙트를 두 번 부르는데,
  //             state 는 비동기로 갱신되므로 가드로 쓰면 지도가 두 개 생긴다.
  //   map     — 렌더가 읽는 값. ref 를 렌더에서 읽으면(종전 코드) 컨텍스트가
  //             ref 변화에 반응하지 않는다. setReady 가 뒤따라서 우연히
  //             맞았을 뿐이다(react-hooks/refs 가 이걸 잡았다).
  const mapRef = useRef<any>(null);
  const [map, setMap] = useState<any>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 지도 탭을 **한 번이라도** 열었는가. 한 번 켜지면 다시 꺼지지 않는다.
  const [everActive, setEverActive] = useState(active);
  useEffect(() => { if (active) setEverActive(true); }, [active]);

  // 지도 1회 초기화.
  //
  // 앱이 뜨자마자 만들지 않는다 — 지도 SDK 는 무거운데, 서울·Platform·Posting·Program
  // 탭만 보는 사용자는 그 비용을 낼 이유가 없다(종전 lazy(MapShell) 이 지키던 성질이다).
  // 대신 한 번 만들면 앱이 닫힐 때까지 그대로 둔다 — 그게 이 컴포넌트의 존재 이유다.
  useEffect(() => {
    if (!everActive || mapRef.current) return;
    let alive = true;
    loadNaverMaps()
      .then(() => {
        if (!alive || !elRef.current || mapRef.current) return;
        const naver = (window as any).naver;
        mapRef.current = new naver.maps.Map(elRef.current, {
          center: new naver.maps.LatLng(GAROSU.lat, GAROSU.lng),
          zoom: 16, scaleControl: false, mapDataControl: false,
        });
        setMap(mapRef.current);
        setReady(true);
      })
      .catch((e) => alive && setError(describeNaverMapError(e)));
    return () => { alive = false; };
  }, [everActive]);

  return (
    <MapHostCtx.Provider value={{ map, ready, error }}>
      <div className={"maphost" + (active ? "" : " is-hidden")} aria-hidden={!active}>
        {/* 지도 캔버스는 탭 순서에서 뺀다 — 키보드 사용자가 지도에 갇히지 않게 */}
        <div ref={elRef} className="map-canvas" tabIndex={-1} />

        {error && (
          <div className="map-note">
            <strong>네이버 지도를 불러오지 못했습니다</strong>
            <div>{error}</div>
            <div>
              NCP 콘솔 &gt; Maps &gt; Application 의 Web 서비스 URL 에{" "}
              <code>{window.location.origin}</code> 을 등록해야 합니다.
            </div>
          </div>
        )}

        {/* 오버레이 — 지도 뷰일 때만 그린다. 지도 자체는 그대로 살아 있다.
            ⚠ 이 래퍼를 벗기지 말 것(2026-09-12). 지도 캔버스는 뷰포트 전체를 쓰는데
            UI 까지 좌측 0 에서 시작하면 검색·목록이 레일(64px) 밑에 깔려 안 눌린다.
            래퍼가 그 폭만큼 비켜서 캔버스와 UI 의 좌측 기준선을 갈라 놓는다
            (MapHost.css `.map-overlays`). */}
        {active && <div className="map-overlays">{children}</div>}
      </div>
    </MapHostCtx.Provider>
  );
}
