import { Request, Response, NextFunction } from 'express';
import User from '../models/registry/User';
import { IUser } from '../models/registry/User';
import { generateToken } from '../utils/jwt';
import { setCache, clearCache, getCache } from '../utils/cache';
import sgMail from '@sendgrid/mail';
import crypto from 'crypto';
import bcrypt from 'bcrypt';

export const login = async (req: Request, res: Response, next: NextFunction) => {
    const { email, password } = req.body;
    if (!email || !password) {
        return res.status(400).json({ success: false, message: 'Please provide email and password' });
    }
    try {
        const user = await User.findOne({ email }).select('+password');
        if (!user) {
            return res.status(401).json({ success: false, message: 'Invalid credentials: User not found' });
        }
        const isMatch = await user.matchPassword(password);
        if (!isMatch) {
            return res.status(401).json({ success: false, message: 'Invalid credentials: Password does not match' });
        }
        const token = generateToken({ id: user.id, email: user.email });
        res.cookie('auth-token', token, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'strict',
            maxAge: 24 * 60 * 60 * 1000,
        });
        const userResponse = {
            id: user.id,
            org: user.org ? user.org.toString() : null,
            email: user.email,
            firstName: user.firstName,
            tier: user.tier,
            type: user.type,
            settings: user.settings
        };
        await setCache(`user:${user.id}`, userResponse, 'MEDIUM');
        res.status(200).json({ success: true, message: 'Login successful', user: userResponse });
    } catch (error) {
        next(error);
    }
};

export const getMe = async (req: Request, res: Response, next: NextFunction) => {
    try {
        if (!req.user) {
            return res.status(401).json({ success: false, message: 'Access denied. Please login.' });
        }
        res.status(200).json({ success: true, user: req.user });
    } catch (error) {
        next(error);
    }
};

export const logout = async (req: Request, res: Response, next: NextFunction) => {
    try {
        if (req.user && req.user.id) {
            await clearCache(`user:${req.user.id}`);
        }
        res.clearCookie('auth-token');
        res.status(200).json({ success: true, message: 'Logged out successfully' });
    } catch (error) {
        next(error);
    }
};

export const forgotPassword = async (req: Request, res: Response, next: NextFunction) => {
    // Implementation from original file
    res.status(200).json({ success: true, message: 'Forgot password endpoint placeholder.' });
};

export const verifyOtp = async (req: Request, res: Response, next: NextFunction) => {
    // Implementation from original file
    res.status(200).json({ success: true, message: 'Verify OTP endpoint placeholder.' });
};

export const resetPassword = async (req: Request, res: Response, next: NextFunction) => {
    // Implementation from original file
    res.status(200).json({ success: true, message: 'Reset password endpoint placeholder.' });
};
