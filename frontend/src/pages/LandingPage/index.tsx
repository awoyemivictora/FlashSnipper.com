import { Button } from "@/components/ui/Button";
import { ComponentNodeSection, FeaturesListSection, FeaturesSection, ImageGallerySection, LayoutSection, MainContentSection, OverlapGroupSection, OverlapSection } from "@/sections";
import { HeroSection } from "@/sections";
import React from "react";
import { Link } from "react-router-dom";

const LandingPage = (): JSX.Element => {
  const navigationItems = [
    { label: "Home", active: true },
    { label: "Features", active: false },
    { label: "Pricing", active: false },
    { label: "FAQs", active: false },
  ];

  return (
    <div className="relative w-full min-h-screen overflow-x-hidden">
      {/* Navigation Bar */}
      <nav className="fixed top-4 left-1/2 transform -translate-x-1/2 z-50 px-4 py-5">
        <div className="flex items-center justify-between gap-6 p-2 bg-[#ffffff1a] rounded-[48px] border border-solid border-[#10b98133] backdrop-blur-[3.5px] backdrop-brightness-[100%] [-webkit-backdrop-filter:blur(3.5px)_brightness(100%)] shadow-lg">
          {/* Logo with TURBOSNIPER text */}
          <div className="flex items-center justify-center gap-3 px-2 py-1">
            <div className="flex items-center gap-2">
              {/* Spiral green spring logo */}
              <div className="w-6 h-6 relative">
                <div className="absolute inset-0 rounded-full bg-gradient-to-br from-emerald-400 to-green-600 animate-pulse shadow-[0_0_10px_rgba(16,185,129,0.5)]">
                  <div className="absolute inset-1 rounded-full border border-emerald-300/50"></div>
                </div>
                <div
                  className="absolute inset-1 rounded-full bg-gradient-to-br from-emerald-200 to-emerald-500 opacity-70 animate-spin"
                  style={{ animationDuration: "3s" }}
                ></div>
              </div>
              {/* Two-tone TURBOSNIPER text */}
              <span className="font-bold text-sm tracking-wider">
                <span className="text-white">FLASH</span>
                <span className="text-[#10B981]">SNIPPER</span>
              </span>
            </div>
          </div>

          {/* Navigation Items - Hidden on mobile, shown on tablet and up */}
          <div className="hidden md:flex items-center gap-1">
            {navigationItems.map((item, index) => (
              <div
                key={`nav-item-${index}`}
                className="flex items-center justify-center gap-2.5 px-4 py-2 rounded-[50px] overflow-hidden hover:bg-white/10 cursor-pointer transition-colors"
              >
                <div className="text-sm font-medium text-white tracking-wide whitespace-nowrap">
                  {item.label}
                </div>
              </div>
            ))}
          </div>

          {/* Mobile Menu Button - Shown only on mobile */}
          <Link to="/trading-interface" aria-label="Open trading interface">
            <button className="md:hidden text-white p-2">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-6 w-6"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 6h16M4 12h16M4 18h16"
                />
              </svg>
            </button>
          </Link>

          {/* Launch Button - Hidden on mobile, shown on tablet and up */}
          <Link to="/trading-interface">
            <Button className="hidden md:flex items-center justify-center gap-2.5 px-6 py-2.5 bg-emerald-500 rounded-[50px] overflow-hidden hover:bg-emerald-600 transition-colors shadow-lg">
              <span className="font-small-text-medium font-[number:var(--small-text-medium-font-weight)] text-white text-[length:var(--small-text-medium-font-size)] tracking-[var(--small-text-medium-letter-spacing)] leading-[var(--small-text-medium-line-height)] whitespace-nowrap [font-style:var(--small-text-medium-font-style)]">
                Launch Sniper
              </span>
            </Button>
          </Link>
        </div>
      </nav>

      {/* Hero Section */}
      <HeroSection />

      {/* Additional sections (commented out for now) */}
      {/* 
      <div className="w-full">
        <FeaturesSection />
        <OverlapSection />
        <OverlapGroupSection />
        <FeaturesListSection />
        <MainContentSection />
        <ComponentNodeSection />
        <LayoutSection />
        <ImageGallerySection />
      </div> 
      */}
    </div>
  );
};

export default LandingPage;
