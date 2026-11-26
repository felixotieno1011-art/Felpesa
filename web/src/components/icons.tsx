import type { ReactNode, SVGProps } from "react";

type P = Omit<SVGProps<SVGSVGElement>, "size"> & { size?: number | string };

function Svg({ size = 22, strokeWidth = 1.9, children, ...rest }: P & { children: ReactNode }) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" width={size} height={size} viewBox="0 0 24 24"
      fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round"
      strokeLinejoin="round" aria-hidden="true" {...rest}>
      {children}
    </svg>
  );
}

export const Home = (p: P) => (<Svg {...p}><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><path d="M9 22V12h6v10" /></Svg>);
export const Send = (p: P) => (<Svg {...p}><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></Svg>);
export const Receipt = (p: P) => (<Svg {...p}><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z" /><path d="M16 8h-6a2 2 0 1 0 0 4h4a2 2 0 1 1 0 4H8" /><path d="M12 17.5v-11" /></Svg>);
export const History = (p: P) => (<Svg {...p}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /><path d="M12 7v5l4 2" /></Svg>);
export const MoreHorizontal = (p: P) => (<Svg {...p}><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /><circle cx="5" cy="12" r="1" /></Svg>);
export const Plus = (p: P) => (<Svg {...p}><path d="M5 12h14" /><path d="M12 5v14" /></Svg>);
export const ArrowUpFromLine = (p: P) => (<Svg {...p}><path d="m18 9-6-6-6 6" /><path d="M12 3v14" /><path d="M5 21h14" /></Svg>);
export const ArrowDownLeft = (p: P) => (<Svg {...p}><path d="M17 7 7 17" /><path d="M17 17H7V7" /></Svg>);
export const ArrowUpRight = (p: P) => (<Svg {...p}><path d="M7 7h10v10" /><path d="M7 17 17 7" /></Svg>);
export const ShoppingBag = (p: P) => (<Svg {...p}><path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" /><path d="M3 6h18" /><path d="M16 10a4 4 0 0 1-8 0" /></Svg>);
export const Smartphone = (p: P) => (<Svg {...p}><rect width="14" height="20" x="5" y="2" rx="2" ry="2" /><path d="M12 18h.01" /></Svg>);
export const ShieldCheck = (p: P) => (<Svg {...p}><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" /><path d="m9 12 2 2 4-4" /></Svg>);
export const UserCog = (p: P) => (<Svg {...p}><circle cx="9" cy="7" r="4" /><path d="M3 21v-1a6 6 0 0 1 9-5.2" /><circle cx="18" cy="18" r="2" /><path d="M18 14v1.5M18 20.5V22M21.5 16l-1.3.75M15.8 19.25 14.5 20M21.5 20l-1.3-.75M15.8 16.75 14.5 16" /></Svg>);
export const LogOut = (p: P) => (<Svg {...p}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="m16 17 5-5-5-5" /><path d="M21 12H9" /></Svg>);
export const Eye = (p: P) => (<Svg {...p}><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /></Svg>);
export const EyeOff = (p: P) => (<Svg {...p}><path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" /><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" /><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" /><path d="m2 2 20 20" /></Svg>);
export const Mail = (p: P) => (<Svg {...p}><rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" /></Svg>);
export const ChevronRight = (p: P) => (<Svg {...p}><path d="m9 18 6-6-6-6" /></Svg>);
