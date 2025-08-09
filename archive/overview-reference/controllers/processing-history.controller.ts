// src/controllers/processing-history.controller.ts
import { Request, Response } from 'express';
import { getDatabase, DATABASE_NAMES } from '../config/databases';
import { Types } from 'mongoose';

const getActivityDb = () => getDatabase(DATABASE_NAMES.ACTIVITY);

export const getJobById = async (req: Request, res: Response) => {
  try {
    const Job = getActivityDb().model('Job');
    const job = await Job.findById(req.params.jobId);
    if (!job) {
      return res.status(404).json({ success: false, error: 'Job not found' });
    }
    res.status(200).json({ success: true, data: job });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Server Error' });
  }
};

export const getProcessedClaimsByJobId = async (req: Request, res: Response) => {
  try {
    const ProcessedClaim = getActivityDb().model('ProcessedClaim');
    // Assuming the job ID is stored on the claim document itself
    const claims = await ProcessedClaim.find({ jobId: new Types.ObjectId(req.params.jobId) });
    res.status(200).json({ success: true, data: claims });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Server Error' });
  }
};

export const getLocationProcessingHistory = async (req: Request, res: Response) => {
  try {
    const Job = getActivityDb().model('Job');
    const history = await Job.find({ locationId: new Types.ObjectId(req.params.locationId) })
                             .sort({ 'timeline.started_at': -1 })
                             .limit(50);
    res.status(200).json({ success: true, data: history });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Server Error' });
  }
};

export const getUserProcessingHistory = async (req: Request, res: Response) => {
  try {
    const Job = getActivityDb().model('Job');
    const history = await Job.find({ userId: new Types.ObjectId(req.params.userId) })
                             .sort({ 'timeline.started_at': -1 })
                             .limit(50);
    res.status(200).json({ success: true, data: history });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Server Error' });
  }
};

export const getClaimById = async (req: Request, res: Response) => {
    try {
        const ProcessedClaim = getActivityDb().model('ProcessedClaim');
        const claim = await ProcessedClaim.findById(req.params.claimId);
        if (!claim) {
            return res.status(404).json({ success: false, message: "Claim not found" });
        }
        res.status(200).json({ success: true, data: claim });
    } catch (error) {
        res.status(500).json({ success: false, error: "Server Error" });
    }
};
