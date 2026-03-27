import { AssetLiveWorkspace } from "../../../components/asset-live-workspace";

type AssetPageProps = {
  params: Promise<{ symbol: string }>;
  searchParams?: Promise<{
    market?: string | string[];
    timeframe?: string | string[];
  }>;
};

export default async function AssetPage({ params, searchParams }: AssetPageProps) {
  const search = (await searchParams) ?? {};
  const { symbol } = await params;
  const marketType = normalizeMarketType(readSingleParam(search.market));
  const timeframe = readSingleParam(search.timeframe) ?? "1m";

  return (
    <AssetLiveWorkspace
      initialMarketType={marketType}
      initialSymbol={symbol}
      initialTimeframe={timeframe}
    />
  );
}

function readSingleParam(value: string | string[] | undefined): string | undefined {
  if (Array.isArray(value)) {
    return value[0];
  }
  return value;
}

function normalizeMarketType(value: string | undefined): "spot" | "futures" {
  return value === "futures" ? "futures" : "spot";
}
