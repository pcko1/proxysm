import { Composition } from "remotion";
import { ProxysmShowcase } from "./Showcase";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="ProxysmShowcase"
        component={ProxysmShowcase}
        durationInFrames={450}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
