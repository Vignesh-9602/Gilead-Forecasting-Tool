import { useContext } from "react";
import { GlobalContext } from "../context/Provider";

export default function useTherapyArea() {
    const { favState } = useContext(GlobalContext);
    return favState?.selectedTherapyArea;
}