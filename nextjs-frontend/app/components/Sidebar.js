'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  {
    label: 'Main Menu',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
      { href: '/businesses', label: 'Leads / Hunt', icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' },
      { href: '/audits', label: 'Website Audits', icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
      { href: '/outreach', label: 'Email Generator', icon: 'M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
      { href: '/inbox', label: 'Inbox', icon: 'M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z' },
    ],
  },
  {
    label: '[1] Sign Up & SaaS Access',
    items: [
      { href: '/workspace', label: 'Workspace & Roles', icon: 'M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z' },
      { href: '/billing', label: 'Subscription Engine', icon: 'M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z' },
    ],
  },
  {
    label: '[2] Custom Business Finder',
    items: [
      { href: '/finder', label: 'Business Finder', icon: 'M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z' },
    ],
  },
  {
    label: '[3] Lead Management',
    items: [
      { href: '/leads', label: 'Lead Management', icon: 'M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z' },
    ],
  },
  {
    label: '[4] Advanced Audit',
    items: [
      { href: '/advanced-audits', label: 'Advanced Audit', icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
    ],
  },
  {
    label: '[5] AI Copywriter',
    items: [
      { href: '/copywriter', label: 'AI Copywriter', icon: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z' },
    ],
  },
  {
    label: '[6] Multi-Channel Send',
    items: [
      { href: '/channels', label: 'Multi-Channel Send', icon: 'M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z' },
    ],
  },
  {
    label: '[7] Schedule Meeting',
    items: [
      { href: '/meetings', label: 'Schedule Meeting', icon: 'M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
    ],
  },
  {
    label: '[8] Drag-and-Drop Builder',
    items: [
      { href: '/builder', label: 'Drag-and-Drop Builder', icon: 'M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z' },
    ],
  },
  {
    label: 'System',
    items: [
      { href: '/jobs', label: 'Background Jobs', icon: 'M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15' },
      { href: '/settings', label: 'Settings', icon: 'M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4' },
    ],
  },
];

export default function Sidebar({ open }) {
  const pathname = usePathname();

  const isActive = (href) => {
    if (href === '/dashboard') return pathname === '/dashboard';
    if (href === '/settings') return pathname === '/settings';
    return pathname.startsWith(href);
  };

  return (
    <aside
      className={`sticky top-[72px] h-[calc(100vh-72px)] bg-white/80 dark:bg-[#08061a]/80 backdrop-blur-xl border-r border-slate-200/80 dark:border-white/[0.04] w-64 flex-shrink-0 transition-all duration-300 flex flex-col z-20 overflow-hidden ${
        !open ? '-ml-64' : ''
      }`}
    >
      {/* Logo */}
      <div className="p-5 border-b border-slate-200/80 dark:border-white/[0.04] flex items-center h-[72px]">
        <h1 className="text-base font-bold text-slate-900 dark:text-white tracking-tight">OrbiScout</h1>
      </div>

      {/* Navigation */}
      <nav className="flex-1 mt-6 overflow-y-auto pb-6">
        {navItems.map((section, si) => (
          <div key={si}>
            <div className={`px-4 mb-2 text-xs font-bold text-slate-400 dark:text-[#6B6890] uppercase tracking-wider ${si > 0 ? 'mt-6' : ''}`}>
              {section.label}
            </div>
            {section.items.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center px-4 py-2.5 text-sm rounded-xl mx-3 my-1 transition-all duration-200 font-medium ${
                  isActive(item.href)
                    ? 'bg-slate-200/50 dark:bg-white/[0.06] text-slate-900 dark:text-white'
                    : 'text-slate-500 dark:text-[#8E8BA3] hover:text-slate-900 dark:hover:text-white hover:bg-slate-200/30 dark:hover:bg-white/[0.03]'
                }`}
              >
                <svg className="w-5 h-5 mr-3 opacity-80" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={item.icon} />
                  {item.icon2 && (
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d={item.icon2} />
                  )}
                </svg>
                {item.label}
              </Link>
            ))}
          </div>
        ))}
      </nav>

      {/* Sidebar footer */}
      <div className="p-4 border-t border-slate-200/80 dark:border-white/[0.04]">
        <div className="flex items-center">
          <div className="w-9 h-9 rounded-xl bg-slate-200/50 dark:bg-white/[0.04] flex items-center justify-center text-xs font-bold text-slate-600 dark:text-[#C8C4E8] border border-slate-200/80 dark:border-white/[0.06]">
            OS
          </div>
          <div className="ml-3">
            <p className="text-sm font-bold text-slate-900 dark:text-white">OrbiScout</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
