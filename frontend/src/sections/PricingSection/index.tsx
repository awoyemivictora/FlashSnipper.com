import React from "react";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card";

export const PricingSection = (): JSX.Element => {
  const planFeatures = {
    free: [
      "Basic filters (socials, LP, revoked authorities)",
      "Custom RPC endpoints",
      "Real-time token monitoring",
      "Basic sniping capabilities",
    ],
    premium: [
      "All Free plan features",
      "Check Top 10 Holder Percentage",
      "Check Token Bundled Percentage",
      "Check Token Same Block Buys",
      "Advanced rug pull detection",
      "Priority RPC access",
      "24/7 Premium support",
    ],
  };

  return (
    <section className="relative w-full min-h-screen py-20 overflow-hidden bg-gradient-to-b from-[#021C14] via-[#021C14] to-emerald-900/20">
      {/* Background Elements */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Animated gradient orbs */}
        <div className="absolute -top-20 -left-20 w-60 h-60 bg-emerald-500/10 rounded-full blur-3xl animate-pulse"></div>
        <div className="absolute -bottom-20 -right-20 w-60 h-60 bg-cyan-500/10 rounded-full blur-3xl animate-pulse delay-1000"></div>

        {/* Icosahedron decorative element */}
        <div className="absolute top-1/4 -left-20 w-48 h-48 opacity-20 blur-lg rotate-12 hidden lg:block">
          <img
            className="w-full h-full object-contain"
            alt="Icosahedron"
            src="https://c.animaapp.com/mcs1777vCoVcpz/img/icosahedron-1-1.png"
          />
        </div>
      </div>

      <div className="relative container mx-auto px-4 sm:px-6 lg:px-8 max-w-7xl">
        {/* Section Header */}
        <div className="text-center mb-16 lg:mb-20">
          <h2 className="text-3xl sm:text-4xl lg:text-5xl font-black bg-gradient-to-b from-white to-emerald-400 bg-clip-text text-transparent mb-6">
            Straightforward Pricing
          </h2>
          <p className="text-lg sm:text-xl text-white/80 max-w-3xl mx-auto leading-relaxed">
            Select the plan that suits your requirements. Begin for free, or
            access premium features for enhanced sniping capabilities! 🚀
          </p>
        </div>

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-12 max-w-6xl mx-auto mb-12">
          {/* Free Plan Card */}
          <Card className="group relative bg-white/5 backdrop-blur-sm rounded-3xl border border-white/10 hover:border-emerald-400/30 transition-all duration-300 hover:transform hover:-translate-y-2 hover:shadow-2xl hover:shadow-emerald-500/10">
            <CardContent className="p-8 h-full flex flex-col">
              <CardHeader className="p-0 mb-6 border-b border-white/10 pb-6">
                <div className="flex flex-col items-start gap-3">
                  <h3 className="text-2xl font-black text-white group-hover:text-emerald-400 transition-colors duration-300">
                    Free Plan
                  </h3>
                  <p className="text-white/70 leading-relaxed">
                    Includes all features except premium Safety filters. Perfect for trying out the bot and testing strategies.
                  </p>
                </div>
              </CardHeader>

              <div className="flex-1 flex flex-col">
                <div className="mb-6">
                  <div className="text-4xl font-black text-white mb-2">$0</div>
                  <div className="text-white/50">Monthly Subscription</div>
                </div>

                <Button className="w-full bg-gradient-to-r from-emerald-500 to-cyan-600 hover:from-emerald-600 hover:to-cyan-700 rounded-full py-3 text-white font-semibold transition-all duration-300 hover:shadow-lg hover:shadow-emerald-500/25 mb-8">
                  Get Started Free
                </Button>

                <CardFooter className="p-0">
                  <div className="w-full">
                    <h4 className="text-white font-semibold mb-4">Includes:</h4>
                    <div className="space-y-3">
                      {planFeatures.free.map((feature, index) => (
                        <div
                          key={`free-feature-${index}`}
                          className="flex items-start gap-3 group-hover:translate-x-1 transition-transform duration-300"
                        >
                          <div className="w-5 h-5 bg-emerald-500 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                            <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                          <span className="text-white/80 text-sm leading-relaxed">{feature}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardFooter>
              </div>

              {/* Hover effect line */}
              <div className="absolute bottom-0 left-0 w-0 h-1 bg-gradient-to-r from-emerald-400 to-cyan-400 group-hover:w-full transition-all duration-500"></div>
            </CardContent>
          </Card>

          {/* Premium Plan Card - Featured */}
          <Card className="group relative bg-gradient-to-br from-emerald-500/10 to-cyan-600/10 backdrop-blur-sm rounded-3xl border border-emerald-400/30 hover:border-emerald-400/50 transition-all duration-300 hover:transform hover:-translate-y-2 hover:shadow-2xl hover:shadow-emerald-500/20">
            {/* Popular Badge */}
            <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
              <div className="bg-gradient-to-r from-emerald-500 to-cyan-600 text-white text-xs font-bold px-4 py-1 rounded-full whitespace-nowrap">
                MOST POPULAR
              </div>
            </div>

            <CardContent className="p-8 h-full flex flex-col">
              <CardHeader className="p-0 mb-6 border-b border-emerald-400/20 pb-6">
                <div className="flex flex-col items-start gap-3">
                  <h3 className="text-2xl font-black text-white group-hover:text-emerald-300 transition-colors duration-300">
                    Premium Plan
                  </h3>
                  <p className="text-white/70 leading-relaxed">
                    Includes all features for serious traders and gives you maximum protection against rug pulls and scams.
                  </p>
                </div>
              </CardHeader>

              <div className="flex-1 flex flex-col">
                <div className="mb-6">
                  <div className="text-4xl font-black text-white mb-2">$99</div>
                  <div className="text-white/50">Monthly Subscription</div>
                </div>

                <Button className="w-full bg-gradient-to-r from-emerald-400 to-cyan-500 hover:from-emerald-300 hover:to-cyan-400 rounded-full py-3 text-gray-900 font-bold transition-all duration-300 hover:shadow-lg hover:shadow-cyan-500/25 mb-8">
                  Get Premium Now
                </Button>

                <CardFooter className="p-0">
                  <div className="w-full">
                    <h4 className="text-white font-semibold mb-4">Everything in Free, plus:</h4>
                    <div className="space-y-3">
                      {planFeatures.premium.map((feature, index) => (
                        <div
                          key={`premium-feature-${index}`}
                          className="flex items-start gap-3 group-hover:translate-x-1 transition-transform duration-300"
                        >
                          <div className="w-5 h-5 bg-cyan-400 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                            <svg className="w-3 h-3 text-gray-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          </div>
                          <span className="text-white/80 text-sm leading-relaxed">{feature}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </CardFooter>
              </div>

              {/* Hover effect line */}
              <div className="absolute bottom-0 left-0 w-0 h-1 bg-gradient-to-r from-cyan-400 to-blue-400 group-hover:w-full transition-all duration-500"></div>
            </CardContent>
          </Card>
        </div>

        {/* Limited Time Offer Banner */}
        <div className="text-center">
          <div className="inline-flex items-center justify-center gap-3 bg-gradient-to-r from-emerald-600/20 to-cyan-600/20 backdrop-blur-sm border border-emerald-400/30 rounded-2xl px-6 py-4 max-w-2xl mx-auto">
            <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse"></div>
            <p className="text-white/90 text-sm sm:text-base">
              <span className="font-semibold text-emerald-300">Limited Time:</span> Once the offer expires, the price will go up and availability may be limited. Act fast to lock in your savings today!
            </p>
          </div>
        </div>

        {/* Additional Info - Fully Responsive */}
        <div className="text-center mt-8 sm:mt-12">
          <div className="flex flex-row justify-center items-center gap-4 sm:gap-6 lg:gap-8 max-w-4xl mx-auto text-white/60">
            {/* Secure Payment */}
            <div className="flex flex-col items-center gap-1 sm:gap-2 min-w-[80px] sm:min-w-0">
              <div className="w-6 h-6 sm:w-8 sm:h-8 bg-emerald-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                <svg className="w-3 h-3 sm:w-4 sm:h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <span className="text-xs sm:text-sm whitespace-nowrap">Secure Payment</span>
            </div>

            {/* Divider */}
            <div className="w-px h-6 bg-white/20 hidden sm:block"></div>

            {/* Cancel Anytime */}
            <div className="flex flex-col items-center gap-1 sm:gap-2 min-w-[80px] sm:min-w-0">
              <div className="w-6 h-6 sm:w-8 sm:h-8 bg-emerald-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                <svg className="w-3 h-3 sm:w-4 sm:h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </div>
              <span className="text-xs sm:text-sm whitespace-nowrap">Cancel Anytime</span>
            </div>

            {/* Divider */}
            <div className="w-px h-6 bg-white/20 hidden sm:block"></div>

            {/* 7-Day Support */}
            <div className="flex flex-col items-center gap-1 sm:gap-2 min-w-[80px] sm:min-w-0">
              <div className="w-6 h-6 sm:w-8 sm:h-8 bg-emerald-500/20 rounded-full flex items-center justify-center flex-shrink-0">
                <svg className="w-3 h-3 sm:w-4 sm:h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M18.364 5.636l-3.536 3.536m0 5.656l3.536 3.536M9.172 9.172L5.636 5.636m3.536 9.192L5.636 18.364M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <span className="text-xs sm:text-sm whitespace-nowrap">7-Day Support</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};