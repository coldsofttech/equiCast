import { useEffect, useRef, useState } from "react";

/**
 * Horizontally-scrolling, snap-aligned carousel for the "Coming next"
 * roadmap cards. Touch/trackpad scrolling is native (overflow-x + scroll-
 * snap); pointer-drag is added on top for mouse users, who otherwise have
 * no way to drag a scroll container. Dots reflect whichever card's left
 * edge is closest to the track's own left edge, and jump-scroll on click.
 */
function RoadmapCarousel({ groups }) {
  const trackRef = useRef(null);
  const cardRefs = useRef([]);
  const dragRef = useRef(null);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const track = trackRef.current;
    if (!track) return undefined;

    const handleScroll = () => {
      const trackLeft = track.getBoundingClientRect().left;
      let closestIndex = 0;
      let closestDistance = Infinity;
      cardRefs.current.forEach((card, index) => {
        if (!card) return;
        const distance = Math.abs(card.getBoundingClientRect().left - trackLeft);
        if (distance < closestDistance) {
          closestDistance = distance;
          closestIndex = index;
        }
      });
      setActiveIndex(closestIndex);
    };

    track.addEventListener("scroll", handleScroll, { passive: true });
    return () => track.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToIndex = (index) => {
    cardRefs.current[index]?.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
  };

  const handlePointerDown = (event) => {
    if (event.pointerType !== "mouse") return;
    const track = trackRef.current;
    if (!track) return;
    dragRef.current = { startX: event.clientX, startScrollLeft: track.scrollLeft };
    track.setPointerCapture(event.pointerId);
  };

  const handlePointerMove = (event) => {
    const drag = dragRef.current;
    const track = trackRef.current;
    if (!drag || !track) return;
    track.scrollLeft = drag.startScrollLeft - (event.clientX - drag.startX);
  };

  const handlePointerUp = (event) => {
    if (!dragRef.current) return;
    dragRef.current = null;
    trackRef.current?.releasePointerCapture(event.pointerId);
  };

  return (
    <div className="ec-roadmap-carousel">
      <div
        className="ec-roadmap-track"
        ref={trackRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        {groups.map((group, index) => (
          <div className="ec-roadmap-card" key={group.title} ref={(el) => (cardRefs.current[index] = el)}>
            <span className="ec-roadmap-tag">{group.tag}</span>
            <h3>{group.title}</h3>
            <ul className="ec-roadmap-list">
              {group.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="ec-roadmap-dots" role="tablist" aria-label="Roadmap categories">
        {groups.map((group, index) => (
          <button
            key={group.title}
            type="button"
            role="tab"
            className={`ec-roadmap-dot${index === activeIndex ? " ec-roadmap-dot--active" : ""}`}
            aria-selected={index === activeIndex}
            aria-label={`Show ${group.title}`}
            onClick={() => scrollToIndex(index)}
          />
        ))}
      </div>
    </div>
  );
}

export default RoadmapCarousel;
